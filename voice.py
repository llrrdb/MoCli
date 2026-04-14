# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
voice.py - MoCli 语音管理器
================================
职责：
  - 统一管理 KWS/STT/TTS 三大协程的后台线程
  - 提供跨线程信号桥（VoiceSignals、AppSignals）
  - PTT (Push-To-Talk) 智能触发状态机
"""

import asyncio
import logging
import threading
import time
from collections import deque

import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal

from db import DBManager
from tts import TTSEngine

# 有条件导入语音模块（缺失依赖时优雅退化）
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    from wakeup import WakeupEngine
    HAS_WAKEUP = True
except ImportError:
    HAS_WAKEUP = False

try:
    from stt import STTEngine
    HAS_STT = True
except ImportError:
    HAS_STT = False

logger = logging.getLogger(__name__)


# ==========================================
# 跨线程信号桥
# ==========================================
class AppSignals(QObject):
    """AI 后台线程 → Qt 主线程的信号桥（用于安全更新 UI）"""
    update_text = pyqtSignal(str)       # 更新气泡文字
    move_to = pyqtSignal(int, int)      # 三角形飞向坐标 (单点时代保留用)
    request_tts = pyqtSignal(str)       # 请求 TTS 朗读
    set_action_state = pyqtSignal(str)  # 更新光标颜色/形状状态
    
    # --- 多点同步巡航新增专线信号 ---
    cursor_fly_and_hold = pyqtSignal(int, int, str)  # 飞往新点位并驻留，携带标签
    cursor_return = pyqtSignal()                     # 打点巡航结束，触发归位
    bubble_sync = pyqtSignal(str)                    # 同步刷新上方的语音文字双轨气泡

class VoiceSignals(QObject):
    """语音引擎 → Qt 主线程的信号桥"""
    wakeup_detected = pyqtSignal()
    stt_result = pyqtSignal(str)
    status_update = pyqtSignal(str)
    tts_state_changed = pyqtSignal(bool)


# ==========================================
# 语音管理器（方案A：共享 asyncio 事件循环）
# ==========================================
class VoiceManager:
    """
    统一管理 KWS/STT/TTS 三大协程的后台线程。
    逻辑文件各自分开，运行时共享同一个 asyncio 事件循环。
    """

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 480    # 30ms 每帧

    def __init__(self, db: DBManager, signals: VoiceSignals, app_signals: AppSignals = None):
        self.db = db
        self.signals = signals
        self.app_signals = app_signals
        self.loop = None
        self._thread = None

        # 子引擎实例
        self.wakeup_engine = WakeupEngine() if HAS_WAKEUP else None
        self.stt_engine = STTEngine() if HAS_STT else None
        # 下放 app_signals 将界面的完全控制权全托管给语音引擎列队枢纽
        self.tts_engine = TTSEngine(db, app_signals=app_signals) if TTSEngine.is_available() else None

        # TTS 状态回调 → 信号
        if self.tts_engine:
            self.tts_engine.set_state_callback(
                lambda active: self.signals.tts_state_changed.emit(active)
            )

        # PTT (Push-To-Talk) 事件标志
        self._ptt_event = None           # 在 asyncio 循环内初始化
        self._stop_recording_event = None  # 强制结束录音事件
        self._pipeline_state = "idle"    # 语音管线状态: idle / listening / recording / processing

    def can_wakeup(self) -> bool:
        """检查 KWS+STT 是否可用（依赖 + 模型 + 设置开关）"""
        if not self.db.get_bool("wakeup_enabled"):
            return False
        if not (self.wakeup_engine and self.wakeup_engine.is_available()):
            return False
        if not (self.stt_engine and self.stt_engine.is_available()):
            return False
        if not HAS_PYAUDIO:
            return False
        return True

    def can_tts(self) -> bool:
        """检查 TTS 是否可用"""
        if not self.db.get_bool("tts_enabled"):
            return False
        return self.tts_engine is not None and TTSEngine.is_available()

    def can_stt(self) -> bool:
        """检查 STT 是否可用（不依赖唤醒开关，用于 PTT 模式）"""
        if not (self.stt_engine and self.stt_engine.is_available()):
            return False
        if not HAS_PYAUDIO:
            return False
        return True

    def start(self):
        """启动语音管理器后台线程"""
        has_wakeup = self.can_wakeup()
        has_stt = self.can_stt()     # STT 可用即可启动麦克风（为 PTT 服务）
        has_tts = self.can_tts()

        if not has_wakeup and not has_stt and not has_tts:
            logger.info("所有语音功能关闭或不可用")
            return False

        mode = []
        if has_wakeup:
            mode.append("KWS+STT")
        elif has_stt:
            mode.append("PTT+STT")  # 没开唤醒但 STT 可用，仅 F10 触发
        if has_tts:
            mode.append("TTS")
        logger.info("启动语音引擎: %s", " + ".join(mode))

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def request_tts(self, text: str):
        """线程安全：将文本投递给 TTS 朗读"""
        if self.tts_engine and self.loop and self.db.get_bool("tts_enabled"):
            self.tts_engine.request_tts(text, self.loop)

    def trigger_ptt(self):
        """
        线程安全：F10 智能触发。
        - 待机/监听中 → 进入等待人声状态
        - 等待人声/录音中 → 强制结束并提交识别
        - 识别/AI 处理中 → 忽略
        """
        if not self.loop or not self.loop.is_running():
            return

        state = self._pipeline_state
        if state in ("idle", "listening"):
            if self._ptt_event:
                self.loop.call_soon_threadsafe(self._ptt_event.set)
        elif state in ("awaiting_speech", "recording"):
            if self._stop_recording_event:
                logger.info("F10 再次按下，结束录音...")
                self.loop.call_soon_threadsafe(self._stop_recording_event.set)
        else:
            logger.debug("正在处理中，忽略 F10")

    def _set_pipeline_state(self, state: str):
        """统一更新管线状态"""
        self._pipeline_state = state

    def _run(self):
        """后台线程入口"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main_async())
        except Exception as e:
            logger.error("引擎异常退出: %s", e, exc_info=True)

    async def _main_async(self):
        """异步主函数：初始化硬件，启动需要的协程"""
        tasks = []
        pa = pyaudio.PyAudio() if HAS_PYAUDIO else None

        # 初始化 TTS 播放
        out_stream = None
        if self.can_tts() and pa:
            self.tts_engine.init_queue()
            out_stream = self.tts_engine.open_speaker(pa)
            tasks.append(self.tts_engine.speaker_loop(out_stream))

        # 初始化 PTT 事件和强制停录事件
        self._ptt_event = asyncio.Event()
        self._stop_recording_event = asyncio.Event()
        self._set_pipeline_state("listening")

        # 初始化 KWS+STT 音频采集与识别流水线
        # 只要 STT 可用就启动麦克风（支持 PTT 模式）
        in_stream = None
        has_wakeup = self.can_wakeup()
        has_stt = self.can_stt()

        if (has_wakeup or has_stt) and pa:
            self.audio_queue = asyncio.Queue(maxsize=200)

            try:
                pa.get_default_input_device_info()
            except OSError:
                logger.error("❌ 未检测到麦克风设备！")
                return

            in_stream = pa.open(
                format=pyaudio.paInt16, channels=1,
                rate=self.SAMPLE_RATE, input=True,
                frames_per_buffer=self.CHUNK_SIZE
            )

            # 加载 STT 模型
            recognizer = self.stt_engine.create_recognizer()
            vad = self.stt_engine.create_vad()

            if recognizer is None:
                logger.error("❌ 语音识别模型不可用，正在停止麦克风管道...")
                if in_stream:
                    in_stream.stop_stream()
                    in_stream.close()
                return

            # 加载 KWS 模型（仅当唤醒开启时）
            kws = None
            if has_wakeup:
                # 从数据库读取已转换好的拼音行列表
                saved_lines = self.db.get("keyword_lines", "")
                if saved_lines:
                    keyword_lines = [l for l in saved_lines.split("\n") if l.strip()]
                else:
                    # fallback：实时转换
                    keyword = self.db.get("wakeup_keyword", "贾维斯")
                    keyword_lines = WakeupEngine.chinese_to_keyword_lines(keyword)
                # 直接传入关键词行，由 create_kws 内部写入临时文件
                kws = self.wakeup_engine.create_kws(keyword_lines)

            tasks.append(self._audio_collector(in_stream))
            tasks.append(self._voice_pipeline(kws, recognizer, vad))

            if has_wakeup:
                keyword = self.db.get("wakeup_keyword", "贾维斯")
                logger.info('✅ 语音引擎就绪！说 "%s" 或按 F10 唤醒', keyword)
            else:
                logger.info('✅ 语音引擎就绪！按 F10 唤醒')

        if not tasks:
            logger.warning("无可用协程，退出")
            return

        try:
            await asyncio.gather(*tasks)
        finally:
            if in_stream:
                in_stream.stop_stream()
                in_stream.close()
            if out_stream:
                out_stream.stop_stream()
                out_stream.close()
            if pa:
                pa.terminate()

    async def _audio_collector(self, in_stream):
        """协程：持续采集麦克风音频数据"""
        while True:
            try:
                data = await asyncio.to_thread(
                    in_stream.read, self.CHUNK_SIZE,
                    exception_on_overflow=False
                )
                # TTS 播放中丢弃麦克风输入，防止回声
                if self.tts_engine and self.tts_engine.is_speaking:
                    continue
                try:
                    self.audio_queue.put_nowait(data)
                except asyncio.QueueFull:
                    while not self.audio_queue.empty():
                        self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("音频采集异常: %s", e)

    async def _voice_pipeline(self, kws, recognizer, vad):
        """
        方案 B 状态机：
        listening → (KWS/PTT) → awaiting_speech → (VAD 确认人声) → recording → (VAD 端点) → processing → listening
                                       ↓ (5s 超时)
                                     listening
        """
        kws_stream = kws.create_stream() if kws else None
        last_trigger = 0.0
        chunks_per_sec = self.SAMPLE_RATE / self.CHUNK_SIZE

        self._set_pipeline_state("listening")

        # VAD 端点检测参数
        voice_end_frames = int(chunks_per_sec * self.stt_engine.VOICE_END_SECONDS)
        max_frames = int(chunks_per_sec * self.stt_engine.MAX_SPEECH_SECONDS)

        # 方案 B 参数
        pre_buffer_size = max(int(chunks_per_sec * 0.3), 1)   # 前 0.3 秒环形缓冲区
        speech_confirm_count = 3                               # 连续 3 帧 VAD 有声确认“有人说话”
        await_timeout_frames = int(chunks_per_sec * 5)         # 5 秒等待超时

        # 统计变量
        pre_buffer = deque(maxlen=pre_buffer_size)
        voice_frames = 0
        silent_frames = 0
        speech_buffer = []
        consecutive_speech = 0
        await_frames = 0

        while True:
            try:
                try:
                    data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # ===== 状态：监听（KWS 唤醒词检测） =====
                if self._pipeline_state == "listening":
                    # 检查 PTT 触发（优先级高于 KWS）
                    if self._ptt_event.is_set():
                        self._ptt_event.clear()
                        logger.info("🎤 F10 触发，等待人声...")

                        # 清空积压队列（键盘声、环境噪音）
                        while not self.audio_queue.empty():
                            try:
                                self.audio_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break

                        self.signals.wakeup_detected.emit()
                        self.signals.status_update.emit("在听呢，请说...")
                        self._set_pipeline_state("awaiting_speech")
                        pre_buffer.clear()
                        consecutive_speech = 0
                        await_frames = 0
                        continue

                    # KWS 流式检测唤醒词
                    if kws is not None:
                        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        result = self.wakeup_engine.process_frame(kws, kws_stream, samples, self.SAMPLE_RATE)
                        if result:
                            now = time.time()
                            if now - last_trigger > self.wakeup_engine.COOLDOWN_SECONDS:
                                last_trigger = now
                                logger.info("🌟 唤醒成功！等待人声...")

                                self.signals.wakeup_detected.emit()
                                self.signals.status_update.emit("在听呢，请说...")
                                self._set_pipeline_state("awaiting_speech")
                                pre_buffer.clear()
                                consecutive_speech = 0
                                await_frames = 0
                                kws_stream = kws.create_stream()

                # ===== 状态：等待人声（环形缓冲 + VAD 确认） =====
                elif self._pipeline_state == "awaiting_speech":
                    # F10 取消
                    if self._stop_recording_event.is_set():
                        self._stop_recording_event.clear()
                        logger.info("用户取消，返回监听")
                        self._set_pipeline_state("listening")
                        self.signals.status_update.emit("")
                        pre_buffer.clear()
                        continue

                    # 持续填充环形缓冲区（保留最近 0.3 秒音频）
                    pre_buffer.append(data)
                    await_frames += 1

                    # VAD 检测是否有人声
                    is_speech = self.stt_engine.is_speech(vad, data, self.SAMPLE_RATE)

                    if is_speech:
                        consecutive_speech += 1
                        if consecutive_speech >= speech_confirm_count:
                            # ✅ 确认有人声！带上预缓冲区开始正式录音
                            logger.info("✅ 检测到人声，开始录音...")
                            self.signals.status_update.emit("正在聆听...")
                            self._set_pipeline_state("recording")
                            speech_buffer = list(pre_buffer)
                            voice_frames = consecutive_speech
                            silent_frames = 0
                    else:
                        consecutive_speech = 0

                    # 等待超时（5 秒内没说话 → 放弃）
                    if await_frames >= await_timeout_frames:
                        logger.info("等待超时，未检测到人声")
                        self._set_pipeline_state("listening")
                        self.signals.status_update.emit("")
                        pre_buffer.clear()

                # ===== 状态：录音中（VAD 端点检测） =====
                elif self._pipeline_state == "recording":
                    # F10 强制结束录音
                    if self._stop_recording_event.is_set():
                        self._stop_recording_event.clear()
                        self._set_pipeline_state("processing")
                        if voice_frames > 6:
                            logger.info("用户手动结束录音，开始识别...")
                            await self._do_stt(recognizer, speech_buffer)
                        else:
                            logger.info("用户手动结束录音，但录音过短，丢弃")
                            self.signals.status_update.emit("")
                        self._set_pipeline_state("listening")
                        speech_buffer = []
                        continue

                    # VAD 端点检测
                    speech_buffer.append(data)
                    is_speech = self.stt_engine.is_speech(vad, data, self.SAMPLE_RATE)

                    if is_speech:
                        voice_frames += 1
                        silent_frames = 0
                    else:
                        silent_frames += 1

                    # 超时保护（上限 20 秒）
                    if len(speech_buffer) > max_frames:
                        self._set_pipeline_state("processing")
                        if voice_frames > 6:
                            await self._do_stt(recognizer, speech_buffer)
                        else:
                            logger.info("录音超时，未检测到有效语音")
                            self.signals.status_update.emit("")
                        self._set_pipeline_state("listening")
                        speech_buffer = []
                        continue

                    # 端点判断："说完了"（有过语音活动后静音超过阈值）
                    if voice_frames >= self.stt_engine.VOICE_START_FRAMES and silent_frames >= voice_end_frames:
                        self._set_pipeline_state("processing")
                        if voice_frames > 6:
                            await self._do_stt(recognizer, speech_buffer)
                        else:
                            logger.info("有声帧过少(%d)，可能是噪音，丢弃", voice_frames)
                            self.signals.status_update.emit("")
                        self._set_pipeline_state("listening")
                        speech_buffer = []

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("流水线异常: %s", e, exc_info=True)

    async def _do_stt(self, recognizer, buffer):
        """执行 STT 推理并发射结果信号"""
        try:
            text = self.stt_engine.recognize(recognizer, buffer, self.SAMPLE_RATE)
            if text and len(text.strip()) > 1:
                logger.info("🎤 识别结果: %s", text)
                self.signals.stt_result.emit(text)
            else:
                self.signals.status_update.emit("")
        except Exception as e:
            logger.error("STT 推理异常: %s", e, exc_info=True)
