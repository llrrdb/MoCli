# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
visual_page.py - 视觉感知配置页面
====================================
管理截屏模式（自动 / 开启 / 关闭）。
使用 SettingCardGroup + SettingCard，Fluent Design 风格。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    BodyLabel,
    SettingCard, SettingCardGroup,
    ComboBox,
    FluentIcon,
    ScrollArea,
)

from db import DBManager


class VisualPage(ScrollArea):
    """视觉感知配置页面"""

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("visualPage")
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
        group = SettingCardGroup("视觉感知", self)

        mode_card = SettingCard(
            FluentIcon.CAMERA,
            "截屏模式",
            "配置 AI 是否获取您的屏幕截图",
            self
        )

        self.mode_combo = ComboBox()
        self.mode_combo.addItem("自动 (按需调用)", userData="auto")
        self.mode_combo.addItem("开启 (每次截屏)", userData="on")
        self.mode_combo.addItem("关闭 (从不截屏)", userData="off")
        self.mode_combo.setMinimumWidth(200)

        current_mode = self.db.get("visual_mode", "auto")
        if current_mode == "on":
            self.mode_combo.setCurrentIndex(1)
        elif current_mode == "off":
            self.mode_combo.setCurrentIndex(2)
        else:
            self.mode_combo.setCurrentIndex(0)

        mode_card.hBoxLayout.addWidget(self.mode_combo, 0, Qt.AlignmentFlag.AlignRight)
        mode_card.hBoxLayout.addSpacing(16)
        group.addSettingCard(mode_card)

        self.lay.addWidget(group)

        # 模式说明
        hint = BodyLabel(
            "自动：AI 判断需要时主动请求截屏（推荐）。\n"
            "开启：每次对话都发送截屏（可能造成浪费）。\n"
            "关闭：完全禁用截屏（纯文本对话）。"
        )
        hint.setContentsMargins(12, 0, 12, 0)
        hint.setStyleSheet("color: #767676;")
        self.lay.addWidget(hint)
