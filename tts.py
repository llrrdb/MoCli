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

    def __init__(self, db):
        self.db = db
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
        """持续从播放队列取出 PCM 数据并输出到扬声器"""
        try:
            while True:
                try:
                    chunk = await self.speaker_queue.get()
                    if chunk is None:
                        # 哨兵值：一段语音播放结束
                        await asyncio.sleep(0.3)
                        self.is_speaking = False
                        if self._tts_state_callback:
                            self._tts_state_callback(False)
                        continue
                    await asyncio.to_thread(out_stream.write, chunk)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("播放异常: %s", e)
        finally:
            # 清理 aiohttp Session
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
        """将文本按标点分句后逐句发起 TTS 合成"""
        text = text.strip()
        if not text:
            return

        self.is_speaking = True
        if self._tts_state_callback:
            self._tts_state_callback(True)

        # 从 SQLite 实时读取 TTS 配置
        tts_url = self.db.get("tts_url") or "http://localhost:8100/v1/audio/speech"
        tts_model = self.db.get("tts_model") or "model-base"

        # 按标点分句
        sentences = self._split_sentences(text)

        # 逐句请求 TTS 并流式播放
        for sentence in sentences:
            clean = self._clean_for_tts(sentence)
            if not clean:
                continue
            await self._request_stream(tts_url, tts_model, clean)

        # 发送结束哨兵
        if self.speaker_queue:
            await self.speaker_queue.put(None)

    def _split_sentences(self, text: str) -> list:
        """按中英文标点分句"""
        sentences = []
        current = []
        for char in text:
            current.append(char)
            if char in self.PUNCTUATIONS:
                s = "".join(current).strip()
                if s:
                    sentences.append(s)
                current = []
        remainder = "".join(current).strip()
        if remainder:
            sentences.append(remainder)
        return sentences

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
            # 复用持久化 Session，避免每句都创建新连接
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
