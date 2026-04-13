# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
wakeup.py - MoCli KWS 语音唤醒引擎
=====================================
基于 sherpa-onnx 的流式关键词检测 (Keyword Spotting)。
提供模型加载、唤醒词词典生成（自动拼音转换）和逐帧检测能力。
"""

import os
import tempfile
import logging

# 有条件导入
try:
    import sherpa_onnx
    HAS_SHERPA = True
except ImportError:
    HAS_SHERPA = False

try:
    from pypinyin import lazy_pinyin, Style as PYStyle
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

logger = logging.getLogger(__name__)

# 项目根目录
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class WakeupEngine:
    """KWS 唤醒引擎：负责加载模型、生成词典、逐帧检测唤醒词"""

    # 模型目录（使用脚本所在目录定位，不依赖 CWD）
    MODEL_DIR = os.path.join(_BASE_DIR, "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01")

    # 去重冷却时间（秒）
    COOLDOWN_SECONDS = 1.5

    # sherpa-onnx 支持的声母列表（按长度降序，保证贪婪匹配）
    _INITIALS = sorted(
        ['zh', 'ch', 'sh',
         'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
         'g', 'k', 'h', 'j', 'q', 'x', 'r',
         'z', 'c', 's', 'y', 'w'],
        key=len, reverse=True
    )

    def is_available(self) -> bool:
        """检查 KWS 所需的依赖和模型文件是否就绪"""
        if not HAS_SHERPA:
            logger.info("缺失依赖: sherpa-onnx")
            return False
        if not os.path.isdir(self.MODEL_DIR):
            logger.info("模型目录不存在: %s", self.MODEL_DIR)
            return False
        return True

    # ------------------------------------------------------------------ #
    # 拼音转换核心逻辑
    # ------------------------------------------------------------------ #

    @classmethod
    def _split_one_pinyin(cls, syllable: str) -> list:
        """
        将单个拼音音节拆分为声母和韵母（供 sherpa-onnx 词典使用）。
        例如: 'jiǎ' -> ['j', 'iǎ']  |  'ān' -> ['ān']
        """
        for ini in cls._INITIALS:
            if syllable.startswith(ini):
                rest = syllable[len(ini):]
                return [ini, rest] if rest else [ini]
        return [syllable]

    @classmethod
    def chinese_to_keyword_lines(cls, chinese_text: str) -> list:
        """
        将中文唤醒词转换为 sherpa-onnx 所需的关键词格式。
        仅生成带声调版本（sherpa-onnx tokens.txt 中只有带声调的韵母 token）。

        示例（chinese_text='贾维斯'）:
            'j iǎ w éi s ī @贾维斯'

        参数:
            chinese_text: 纯中文唤醒词，如 '贾维斯'
        返回:
            包含关键词行的列表
        """
        if not HAS_PYPINYIN:
            logger.warning("pypinyin 未安装，无法生成拼音格式唤醒词")
            return []

        # 仅生成带声调版本：sherpa-onnx tokens.txt 中只存在带声调的韵母
        # （如 iǎo, ài, óng, ué），不带声调的版本（iao, ai, ong, ue）会导致
        # "Cannot find ID for token" 编码错误
        toned_parts = []
        for syl in lazy_pinyin(chinese_text, style=PYStyle.TONE):
            toned_parts.extend(cls._split_one_pinyin(syl))
        line = " ".join(toned_parts) + f" @{chinese_text}"
        return [line]

    # ------------------------------------------------------------------ #

    def create_kws(self, keyword_lines: list):
        """
        加载并返回 KeywordSpotter 实例。
        将关键词行写入临时文件（不在项目根目录创建持久文件）供 sherpa-onnx 加载。

        参数:
            keyword_lines: chinese_to_keyword_lines() 返回的行列表
        """
        if not HAS_SHERPA:
            return None

        if not keyword_lines:
            logger.warning("关键词列表为空，无法创建 KWS")
            return None

        # 写入临时文件（sherpa-onnx 需要文件路径，不支持内存传入）
        fd, tmp_path = tempfile.mkstemp(suffix='.txt', prefix='mocli_kw_')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                for line in keyword_lines:
                    f.write(line + "\n")
            logger.info("关键词已写入临时文件 (%d 行)", len(keyword_lines))

            logger.info("⏳ 加载唤醒模型 (KWS)...")
            kws = sherpa_onnx.KeywordSpotter(
                tokens=os.path.join(self.MODEL_DIR, "tokens.txt"),
                encoder=os.path.join(self.MODEL_DIR, "encoder-epoch-99-avg-1-chunk-16-left-64.onnx"),
                decoder=os.path.join(self.MODEL_DIR, "decoder-epoch-99-avg-1-chunk-16-left-64.onnx"),
                joiner=os.path.join(self.MODEL_DIR, "joiner-epoch-99-avg-1-chunk-16-left-64.onnx"),
                keywords_file=tmp_path,
                num_threads=2,
                max_active_paths=4,
                keywords_score=2.0,
                keywords_threshold=0.1,
                provider="cpu"
            )
            logger.info("✅ 唤醒模型就绪")
            return kws
        except Exception as e:
            logger.error("KWS 加载失败: %s", e, exc_info=True)
            return None
        finally:
            # sherpa-onnx 在构造时就读完了文件，可以安全删除
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def process_frame(kws, kws_stream, samples, sample_rate: int = 16000):
        """
        处理一帧音频数据，检测是否包含唤醒词。
        参数:
            kws: KeywordSpotter 实例
            kws_stream: KWS 流
            samples: float32 归一化音频样本 (numpy array)
            sample_rate: 采样率
        返回:
            检测到的关键词字符串，或 None
        """
        kws_stream.accept_waveform(sample_rate, samples)
        while kws.is_ready(kws_stream):
            kws.decode_stream(kws_stream)
        result = kws.get_result(kws_stream)
        return result if result else None
