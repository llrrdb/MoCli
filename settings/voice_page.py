# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
voice_page.py - 语音交互配置页面
===================================
管理语音唤醒 (KWS) 和语音合成 (TTS) 的配置。
使用 SettingCardGroup + SettingCard 组件族，Fluent Design 风格。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    BodyLabel, LineEdit,
    SettingCard, SwitchSettingCard, PushSettingCard,
    SettingCardGroup, FluentIcon,
    ScrollArea,
)

from db import DBManager


class VoicePage(ScrollArea):
    """语音交互配置页面"""

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("voicePage")
        self.setWidgetResizable(True)

        content = QWidget()
        content.setObjectName("scrollContent")
        content.setStyleSheet("QWidget#scrollContent { background: transparent; }")
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.lay = QVBoxLayout(content)
        self.lay.setContentsMargins(36, 28, 36, 28)
        self.lay.setSpacing(20)
        self.setWidget(content)

        self._build()
        self.lay.addStretch()

    def _build(self):
        # ==========================================
        # 卡片组1：语音唤醒 (KWS)
        # ==========================================
        kws_group = SettingCardGroup("语音唤醒", self)

        self._wakeup_card = SwitchSettingCard(
            FluentIcon.MEGAPHONE,
            "启用语音唤醒",
            "说出唤醒词自动激活麦克风，也可按 F10 直接唤醒",
            configItem=None,
            parent=self
        )
        self._wakeup_card.switchButton.setChecked(self.db.get_bool("wakeup_enabled"))
        kws_group.addSettingCard(self._wakeup_card)

        keyword_card = SettingCard(
            FluentIcon.LANGUAGE,
            "唤醒词（纯中文）",
            "例如：贾维斯",
            self
        )
        self.keyword_input = LineEdit()
        self.keyword_input.setText(self.db.get("wakeup_keyword"))
        self.keyword_input.setPlaceholderText("贾维斯")
        self.keyword_input.setMinimumWidth(200)
        keyword_card.hBoxLayout.addWidget(self.keyword_input, 0, Qt.AlignmentFlag.AlignRight)
        keyword_card.hBoxLayout.addSpacing(16)
        kws_group.addSettingCard(keyword_card)

        self.lay.addWidget(kws_group)

        # 拼音预览标签（独立于卡片组）
        self._kw_preview = BodyLabel("拼音预览：（输入唤醒词后自动生成）")
        self._kw_preview.setWordWrap(True)
        self._kw_preview.setContentsMargins(12, 0, 12, 0)
        self._kw_preview.setStyleSheet("color: #767676;")
        saved_lines = self.db.get("keyword_lines", "")
        if saved_lines:
            self._kw_preview.setText("已保存的拼音：" + saved_lines)
        self.lay.addWidget(self._kw_preview)

        # 预览按钮
        preview_btn = PushSettingCard(
            "预览拼音",
            FluentIcon.FONT,
            "拼音预览",
            "点击生成唤醒词的拼音格式供 KWS 使用",
            parent=self
        )
        preview_btn.clicked.connect(self._preview_keyword)
        self.lay.addWidget(preview_btn)
        # 联动：输入变化时自动预览
        self.keyword_input.textChanged.connect(self._preview_keyword)

        # ==========================================
        # 卡片组2：语音合成 (TTS)
        # ==========================================
        tts_group = SettingCardGroup("语音合成", self)

        self._tts_card = SwitchSettingCard(
            FluentIcon.HEADPHONE,
            "启用 AI 语音回复",
            "AI 回复将通过 TTS 服务自动朗读",
            configItem=None,
            parent=self
        )
        self._tts_card.switchButton.setChecked(self.db.get_bool("tts_enabled"))
        tts_group.addSettingCard(self._tts_card)

        tts_url_card = SettingCard(
            FluentIcon.GLOBE,
            "TTS 服务地址",
            "本地或远程 TTS HTTP API 端点",
            self
        )
        self.tts_url_input = LineEdit()
        self.tts_url_input.setText(self.db.get("tts_url"))
        self.tts_url_input.setPlaceholderText("http://localhost:8100/v1/audio/speech")
        self.tts_url_input.setMinimumWidth(280)
        tts_url_card.hBoxLayout.addWidget(self.tts_url_input, 0, Qt.AlignmentFlag.AlignRight)
        tts_url_card.hBoxLayout.addSpacing(16)
        tts_group.addSettingCard(tts_url_card)

        tts_model_card = SettingCard(
            FluentIcon.CODE,
            "TTS 语音模型标识",
            "例如：model-base",
            self
        )
        self.tts_model_input = LineEdit()
        self.tts_model_input.setText(self.db.get("tts_model"))
        self.tts_model_input.setPlaceholderText("model-base")
        self.tts_model_input.setMinimumWidth(200)
        tts_model_card.hBoxLayout.addWidget(self.tts_model_input, 0, Qt.AlignmentFlag.AlignRight)
        tts_model_card.hBoxLayout.addSpacing(16)
        tts_group.addSettingCard(tts_model_card)

        self.lay.addWidget(tts_group)

    # ==========================================
    # 属性别名 — 保持 window.py 兼容
    # ==========================================

    @property
    def wakeup_switch(self):
        """向后兼容：window.py 通过此属性访问开关状态"""
        return self._wakeup_card.switchButton

    @property
    def tts_switch(self):
        """向后兼容：window.py 通过此属性访问开关状态"""
        return self._tts_card.switchButton

    # ==========================================
    # 拼音预览
    # ==========================================

    def _preview_keyword(self):
        from wakeup import WakeupEngine
        text = self.keyword_input.text().strip()
        if not text:
            self._kw_preview.setText("拼音预览：（请输入中文唤醒词）")
            return
        lines = WakeupEngine.chinese_to_keyword_lines(text)
        if lines:
            self._kw_preview.setText("拼音预览：\n" + "\n".join(lines))
        else:
            self._kw_preview.setText("⚠️ pypinyin 未安装，无法生成拼音")
