# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
visual_page.py - 视觉感知配置页面
====================================
管理截屏模式（自动 / 开启 / 关闭）。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    ScrollArea,
)

from db import DBManager
from settings.cards import FluentCard


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

    def _build(self):
        c1 = FluentCard("视觉感知模式", "配置 AI 是否获取您的屏幕截图。")
        row = QHBoxLayout()
        row.addWidget(BodyLabel("截屏模式"))
        row.addStretch()

        self.mode_combo = ComboBox()
        self.mode_combo.addItem("自动 (按需调用)", userData="auto")
        self.mode_combo.addItem("开启 (每次截屏)", userData="on")
        self.mode_combo.addItem("关闭 (从不截屏)", userData="off")

        current_mode = self.db.get("visual_mode", "auto")
        if current_mode == "on":
            self.mode_combo.setCurrentIndex(1)
        elif current_mode == "off":
            self.mode_combo.setCurrentIndex(2)
        else:
            self.mode_combo.setCurrentIndex(0)

        row.addWidget(self.mode_combo)
        c1.add_layout(row)
        c1.add_divider()

        hint = BodyLabel(
            "自动：AI 判断需要时主动请求截屏（推荐）。\n"
            "开启：每次对话都发送截屏（可能造成浪费）。\n"
            "关闭：完全禁用截屏（纯文本对话）。"
        )
        hint.setStyleSheet("color: #767676;")
        c1.add_widget(hint)

        self.lay.addWidget(c1)
        self.lay.addStretch()
