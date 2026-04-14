# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
tts.py - MoCli TTS 文字转语音引擎
====================================
通过 aiohttp 异步请求本地 TTS 服务，流式 PCM 播放。
独立管理扬声器输出流和播放队列。
"""

import re
import asyncio
import logging

# 有条件导入
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)


class TTSEngine:
    """TTS 引擎：文本分句 → 流式 HTTP 请求 → PCM 扬声器播放"""

    # 扬声器参数（24kHz，匹配 TTS 服务输出采样率）
    SAMPLE_RATE_SPK = 24000
    CHUNK_SIZE_SPK = 1024

    # 断句标点
    PUNCTUATIONS = {"。", "！", "？", "；", ".", "!", "?", "\n"}

    def __init__(self, db, app_signals=None):
        self.db = db
        self.app_signals = app_signals
        self.is_speaking = False
        self.speaker_queue = None
        self._tts_state_callback = None  # 可选：TTS 状态回调
        self._session = None             # 持久化 aiohttp Session

    def set_state_callback(self, callback):
        """设置 TTS 播放状态变更回调（True=开始, False=结束）"""
        self._tts_state_callback = callback

    @staticmethod
    def is_available() -> bool:
        """检查 TTS 所需依赖"""
        if not HAS_PYAUDIO:
            logger.info("缺失依赖: pyaudio")
            return False
        if not HAS_AIOHTTP:
            logger.info("缺失依赖: aiohttp")
            return False
        return True

    def init_queue(self):
        """初始化播放队列和 aiohttp Session（需在 asyncio 事件循环内调用）"""
        self.speaker_queue = asyncio.Queue(maxsize=3000)
        self._session = aiohttp.ClientSession()

    def open_speaker(self, pa):
        """打开扬声器输出流"""
        return pa.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.SAMPLE_RATE_SPK, output=True,
            frames_per_buffer=self.CHUNK_SIZE_SPK
        )

    async def speaker_loop(self, out_stream):
        """持续从播放队列取出事件或 PCM 数据（消费者）"""
        current_label = "巡航准备中"
        
        try:
            while True:
                try:
                    chunk = await self.speaker_queue.get()
                    if chunk is None:
                        # 哨兵值：播放结束触发光标返回
                        # 给最后的话音留 2 秒缓冲
                        await asyncio.sleep(2.0)
                        self.is_speaking = False
                        if self._tts_state_callback:
                            self._tts_state_callback(False)
                        if self.app_signals:
                            self.app_signals.cursor_return.emit()
                        continue
                        
                    if isinstance(chunk, dict):
                        # 处理 UI 同步指令事件
                        if chunk["type"] == "sync_text":
                            if self.app_signals:
                                text_content = chunk["content"]
                                display_str = f"🎯 指向：{current_label}\n\n💬 {text_content}"
                                self.app_signals.bubble_sync.emit(display_str)
                                
                        elif chunk["type"] == "point":
                            current_label = chunk["label"]
                            logger.info("队列弹出目标: 飞往 %s (%d, %d)", current_label, chunk['x'], chunk['y'])
                            if self.app_signals:
                                self.app_signals.cursor_fly_and_hold.emit(chunk["x"], chunk["y"], current_label)
                                
                    else:
                        # 真实的音频块，调用系统的扬声器驱动
                        if out_stream and not out_stream.is_stopped():
                            await asyncio.to_thread(out_stream.write, chunk)
                            
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("播放异常: %s", e)
        finally:
            if self._session and not self._session.closed:
                await self._session.close()

    def request_tts(self, text: str, loop):
        """
        线程安全入口：将文本投递给 TTS 异步流进行朗读。
        供 Qt 主线程调用。
        """
        if loop and loop.is_running() and HAS_AIOHTTP:
            asyncio.run_coroutine_threadsafe(self._speak(text), loop)

    async def _speak(self, text: str):
        """解析文本结构，按序请求语音并派发协调指令（生产者）"""
        text = text.strip()
        if not text:
            return

        self.is_speaking = True
        if self._tts_state_callback:
            self._tts_state_callback(True)

        tts_enabled = self.db.get_bool("tts_enabled")
        tts_url = self.db.get("tts_url") or "http://localhost:8100/v1/audio/speech"
        tts_model = self.db.get("tts_model") or "model-base"

        # 使用正则表达式剥离提取 P_POINT 控制事件和伴随文字
        events = self._parse_text_sequence(text)

        # 逐段遍历压入队列
        for event in events:
            if event["type"] == "text":
                content = event["content"]
                # 塞入：即将开始朗读文字的同步 UI 更新信号
                if self.speaker_queue:
                    await self.speaker_queue.put({"type": "sync_text", "content": content})
                
                # 请求语音字节 / 降级模拟睡眠
                clean = self._clean_for_tts(content)
                if clean:
                    if tts_enabled and HAS_AIOHTTP and self.open_speaker:  # 若音频可用，则真的去求合成
                        await self._request_stream(tts_url, tts_model, clean)
                    else:
                        # 兜底：如果没开语音合成，那就按一秒大约 4 个字的阅读速度进行 dummy Sleep 模拟
                        delay = max(1.0, len(clean) * 0.25)
                        logger.info("已跳过语音合成，按字数模拟延时 %.1fs: %s", delay, clean)
                        await asyncio.sleep(delay)
                        
            elif event["type"] == "point":
                if self.speaker_queue:
                    await self.speaker_queue.put(event)

        # 发送一段连续问答流程结束哨兵
        if self.speaker_queue:
            await self.speaker_queue.put(None)

    def _parse_text_sequence(self, full_text: str):
        """将长文本中的 [P_POINT:x,y:标题] 与自然语句分离排队"""
        pattern = r'(\[P_POINT:\d+,\d+:[^\]]+\])'
        parts = re.split(pattern, full_text)
        
        sequence = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            match = re.match(r'\[P_POINT:(\d+),(\d+):([^\]]+)\]', part)
            if match:
                # 若因点位导致劈开了完整短语，强制在上一段短语末尾塞入逗号让大模型喘息
                if sequence and sequence[-1]["type"] == "text" and not sequence[-1]["content"].strip().endswith(("，", "。", "！", "？", "：", "”")):
                    sequence[-1]["content"] = sequence[-1]["content"].rstrip() + "，"

                sequence.append({
                    "type": "point",
                    "x": int(match.group(1)),
                    "y": int(match.group(2)),
                    "label": match.group(3)
                })
            else:
                sequence.append({"type": "text", "content": part})
        return sequence

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """清理文本中不适合朗读的 Markdown 格式标记"""
        text = re.sub(r'[*_]{1,3}', '', text)
        text = re.sub(r'#+\s?', '', text)
        text = re.sub(r'`+', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return text.strip()

    async def _request_stream(self, url: str, model: str, text: str):
        """向 TTS API 发起流式 PCM 合成请求（复用 aiohttp Session）"""
        payload = {"model": model, "input": text, "response_format": "pcm"}
        try:
            session = self._session
            if session is None or session.closed:
                session = aiohttp.ClientSession()
                self._session = session

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    async for chunk in resp.content.iter_chunked(4096):
                        if self.speaker_queue:
                            await self.speaker_queue.put(chunk)
                else:
                    logger.warning("请求失败 (HTTP %d)", resp.status)
        except Exception as e:
            logger.error("网络异常: %s", e)
