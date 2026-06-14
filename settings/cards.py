# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
cards.py - 设置面板通用卡片组件
==================================
提供 Win11 风格的白底圆角容器 FluentCard。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from qfluentwidgets import SubtitleLabel, BodyLabel, setFont


class FluentCard(QFrame):
    """Win11 风格设置卡片：白底圆角容器"""

    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        self.setObjectName("fluentCard")
        self.setStyleSheet("""
            QFrame#fluentCard {
                background-color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(6)

        if title:
            t = SubtitleLabel(title)
            setFont(t, 18, QFont.Weight.DemiBold)
            lay.addWidget(t)
        if description:
            d = BodyLabel(description)
            d.setWordWrap(True)
            d.setStyleSheet("color: #767676;")
            lay.addWidget(d)
        if title or description:
            lay.addSpacing(12)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(12)
        lay.addLayout(self.content_layout)

    def add_widget(self, w: QWidget):
        self.content_layout.addWidget(w)

    def add_layout(self, l):
        self.content_layout.addLayout(l)

    def add_divider(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background: #EEEEEE; max-height: 1px;")
        self.content_layout.addWidget(f)

    def add_row(self, label_text: str, widget: QWidget) -> QWidget:
        """添加 标题+控件 的行"""
        lbl = BodyLabel(label_text)
        lbl.setStyleSheet("color: #4A4A4A; font-weight: 500;")
        self.content_layout.addWidget(lbl)
        widget.setMinimumHeight(36)
        self.content_layout.addWidget(widget)
        return widget
