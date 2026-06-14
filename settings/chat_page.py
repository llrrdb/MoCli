# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
chat_page.py - 聊天对话页面
===============================
提供纯文本对话界面，支持历史记录浏览和清空。
"""

import re
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QMessageBox, QScrollBar,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from qfluentwidgets import (
    SubtitleLabel, BodyLabel,
    LineEdit, PrimaryPushButton, PushButton,
    ScrollArea, setFont,
)

from db import DBManager


class ChatPage(QWidget):
    """聊天对话页面"""

    ask_signal = pyqtSignal(str)
    reply_signal = pyqtSignal(dict)

    def __init__(self, db: DBManager, llm_engine, parent=None):
        super().__init__(parent)
        self.db = db
        self.llm = llm_engine
        self.setObjectName("chatPage")

        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(36, 28, 36, 28)
        self.lay.setSpacing(12)

        # 头部标题
        title = SubtitleLabel("💬 对话")
        setFont(title, 20, QFont.Weight.DemiBold)
        self.lay.addWidget(title)

        # 消息滚动区域
        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #E5E5E5; border-radius: 8px; background: rgba(255, 255, 255, 0.5); }")

        self.msg_container = QWidget()
        self.msg_container.setStyleSheet("background: transparent;")
        self.msg_lay = QVBoxLayout(self.msg_container)
        self.msg_lay.setContentsMargins(16, 16, 16, 16)
        self.msg_lay.setSpacing(16)
        self.msg_lay.addStretch()  # 将消息往上顶

        self.scroll_area.setWidget(self.msg_container)
        self.lay.addWidget(self.scroll_area, stretch=1)

        # 底部输入区域
        input_lay = QHBoxLayout()
        input_lay.setSpacing(12)

        self.input_box = LineEdit()
        self.input_box.setPlaceholderText("在此输入消息 (Enter 发送)...")
        self.input_box.setMinimumHeight(40)
        self.input_box.returnPressed.connect(self._send_msg)

        self.send_btn = PrimaryPushButton("发送")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.clicked.connect(self._send_msg)

        self.clear_btn = PushButton("清空历史")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.clicked.connect(self._clear_history)

        input_lay.addWidget(self.input_box, stretch=1)
        input_lay.addWidget(self.send_btn)
        input_lay.addWidget(self.clear_btn)

        self.lay.addLayout(input_lay)

        # 信号连接
        self.ask_signal.connect(self._do_ask_ai_in_thread)
        self.reply_signal.connect(self._on_ai_reply)

        self._load_history()

    def _add_message_bubble(self, role: str, content: str):
        """在 UI 中添加一条气泡消息"""
        # 清洗 [POINT:x,y:label] 及其衍生标签，只保留 label（为了美观）
        content = re.sub(r'\[P?_?POINT:\d+,\d+:([^\]]+)\]', r'[\1]', content)

        lbl = BodyLabel(content)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # 使用 QFrame 作为气泡背景
        bubble = QFrame()
        bubble_lay = QVBoxLayout(bubble)
        bubble_lay.setContentsMargins(12, 10, 12, 10)
        bubble_lay.addWidget(lbl)

        row_lay = QHBoxLayout()

        if role == "user":
            bubble.setStyleSheet("background-color: #D3E3FD; border-radius: 8px;")
            lbl.setStyleSheet("color: #041E49;")
            row_lay.addStretch()
            row_lay.addWidget(bubble)
        else:
            bubble.setStyleSheet("background-color: #F1F3F4; border-radius: 8px;")
            lbl.setStyleSheet("color: #202124;")
            row_lay.addWidget(bubble)
            row_lay.addStretch()

        # 插入在弹簧之前
        self.msg_lay.insertLayout(self.msg_lay.count() - 1, row_lay)

        # 滚动到底部
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))

    def _load_history(self):
        """初始加载数据库历史记录"""
        history = self.db.get_chat_history()
        for msg in history:
            self._add_message_bubble(msg["role"], msg["content"])

    def _send_msg(self):
        text = self.input_box.text().strip()
        if not text:
            return

        # 1. UI 更新：添加用户气泡，清空输入框
        self._add_message_bubble("user", text)
        self.input_box.clear()

        # 2. 状态更新：禁用输入
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.input_box.setPlaceholderText("正在思考...")

        # 3. 触发后续步骤（在后台线程进行）
        self.ask_signal.emit(text)

    def _do_ask_ai_in_thread(self, text: str):
        """在新线程中执行请求"""
        def worker():
            try:
                result = self.llm.ask(text)
                self.reply_signal.emit(result)
            except Exception as e:
                self.reply_signal.emit({"error": str(e), "spoken_text": ""})

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_reply(self, result: dict):
        """AI 处理完成回到主线程"""
        # 恢复状态
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setPlaceholderText("在此输入消息 (Enter 发送)...")
        self.input_box.setFocus()

        if result.get("error"):
            self._add_message_bubble("assistant", f"⚠️ 错误：{result['error']}")
        else:
            reply_text = result.get("raw_text", "(无回应)")
            self._add_message_bubble("assistant", reply_text)

    def _clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(self, "确认清空", "确认要清空所有聊天记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_chat_history()
            # 清除 UI (保留最后的弹簧)
            while self.msg_lay.count() > 1:
                item = self.msg_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        subitem = item.layout().takeAt(0)
                        if subitem.widget():
                            subitem.widget().deleteLater()
                    item.layout().deleteLater()
