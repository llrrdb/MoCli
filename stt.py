# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
stt.py - MoCli STT 语音转文字引擎
====================================
基于 SenseVoice 的离线语音识别，配合 WebRTC VAD 实现端点检测。
"""

import os
import logging

# 有条件导入
try:
    import sherpa_onnx
    HAS_SHERPA = True
except ImportError:
    HAS_SHERPA = False

try:
    import webrtcvad
    HAS_VAD = True
except ImportError:
    HAS_VAD = False

logger = logging.getLogger(__name__)

# 项目根目录
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class STTEngine:
    """STT 引擎：负责 VAD 端点检测和 SenseVoice 离线推理"""

    # 模型目录（使用脚本所在目录定位，不依赖 CWD）
    MODEL_DIR = os.path.join(_BASE_DIR, "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17")

    # VAD 参数
    VAD_MODE = 1                  # WebRTC VAD 灵敏度 (0-3)
    VOICE_START_FRAMES = 6        # 连续有声帧达到此值才算"开始说话" (约180ms，抵抗机械键盘按击声)
    VOICE_END_SECONDS = 0.8       # 静音超过此秒数算"说完了"
    MAX_SPEECH_SECONDS = 20       # 单次录音最大时长保护

    def is_available(self) -> bool:
        """检查 STT 所需的依赖和模型文件是否就绪"""
        if not HAS_SHERPA:
            logger.info("缺失依赖: sherpa-onnx")
            return False
        if not HAS_VAD:
            logger.info("缺失依赖: webrtcvad")
            return False
        if not os.path.isdir(self.MODEL_DIR):
            logger.info("模型目录不存在: %s", self.MODEL_DIR)
            return False
        return True

    def create_recognizer(self):
        """加载并返回 OfflineRecognizer 实例"""
        if not HAS_SHERPA:
            return None

        logger.info("⏳ 加载语音识别模型 (SenseVoice)...")
        try:
            recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=os.path.join(self.MODEL_DIR, "model.int8.onnx"),
                tokens=os.path.join(self.MODEL_DIR, "tokens.txt"),
                num_threads=2,
                use_itn=True
            )
            logger.info("✅ 语音识别模型就绪")
            return recognizer
        except Exception as e:
            logger.error("❌ 加载 SenseVoice 模型失败！详情: %s", e)
            logger.error("提示: 可能是由于缺失 ONNX Runtime 或者 API 版本不匹配引起。请检查 sherpa-onnx 依赖。")
            return None

    def create_vad(self):
        """创建 WebRTC VAD 实例（使用类属性 VAD_MODE）"""
        if not HAS_VAD:
            return None
        return webrtcvad.Vad(self.VAD_MODE)

    @staticmethod
    def is_speech(vad, audio_data: bytes, sample_rate: int = 16000) -> bool:
        """检测一帧音频是否包含语音活动"""
        if vad is None:
            return False
        return vad.is_speech(audio_data, sample_rate)

    @staticmethod
    def recognize(recognizer, audio_buffer: list, sample_rate: int = 16000) -> str:
        """
        对录音缓冲区执行离线 STT 推理。
        参数:
            recognizer: OfflineRecognizer 实例
            audio_buffer: list[bytes]，每个元素是一帧 16bit PCM
            sample_rate: 采样率
        返回:
            识别结果文本
        """
        import numpy as np

        audio_bytes = b"".join(audio_buffer)
        samples = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )

        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()
