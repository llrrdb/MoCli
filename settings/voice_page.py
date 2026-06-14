# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
voice_page.py - 语音交互配置页面
===================================
管理语音唤醒 (KWS) 和语音合成 (TTS) 的配置。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton,
    SwitchButton,
    ScrollArea,
)

from db import DBManager
from settings.cards import FluentCard


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

    def _build(self):
        # 卡片1：语音唤醒
        c1 = FluentCard("语音唤醒 (KWS)", "说出唤醒词自动激活麦克风，也可按 F10 直接唤醒。")
        row_wake = QHBoxLayout()
        row_wake.addWidget(BodyLabel("启用语音唤醒"))
        row_wake.addStretch()
        self.wakeup_switch = SwitchButton()
        self.wakeup_switch.setChecked(self.db.get_bool("wakeup_enabled"))
        row_wake.addWidget(self.wakeup_switch)
        c1.add_layout(row_wake)
        c1.add_divider()

        self.keyword_input = LineEdit()
        self.keyword_input.setText(self.db.get("wakeup_keyword"))
        self.keyword_input.setPlaceholderText("贾维斯")
        c1.add_row("唤醒词（纯中文）", self.keyword_input)

        self._kw_preview = BodyLabel("拼音预览：（输入唤醒词后自动生成）")
        self._kw_preview.setWordWrap(True)
        self._kw_preview.setStyleSheet("color: #767676;")
        c1.add_widget(self._kw_preview)

        preview_btn = PushButton("预览拼音")
        preview_btn.setMinimumHeight(36)
        preview_btn.clicked.connect(self._preview_keyword)
        c1.add_widget(preview_btn)

        # 初始化预览
        saved_lines = self.db.get("keyword_lines", "")
        if saved_lines:
            self._kw_preview.setText("已保存的拼音：" + saved_lines)
        self.keyword_input.textChanged.connect(self._preview_keyword)
        self.lay.addWidget(c1)

        # 卡片2：语音合成
        c2 = FluentCard("语音合成 (TTS)", "AI 回复将通过 TTS 服务自动朗读。")
        row_tts = QHBoxLayout()
        row_tts.addWidget(BodyLabel("启用 AI 语音回复"))
        row_tts.addStretch()
        self.tts_switch = SwitchButton()
        self.tts_switch.setChecked(self.db.get_bool("tts_enabled"))
        row_tts.addWidget(self.tts_switch)
        c2.add_layout(row_tts)
        c2.add_divider()

        self.tts_url_input = LineEdit()
        self.tts_url_input.setText(self.db.get("tts_url"))
        self.tts_url_input.setPlaceholderText("http://localhost:8100/v1/audio/speech")
        c2.add_row("TTS 服务地址", self.tts_url_input)
        c2.add_divider()

        self.tts_model_input = LineEdit()
        self.tts_model_input.setText(self.db.get("tts_model"))
        self.tts_model_input.setPlaceholderText("model-base")
        c2.add_row("TTS 语音模型标识", self.tts_model_input)
        self.lay.addWidget(c2)

        self.lay.addStretch()

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
