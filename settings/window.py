# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
window.py - SettingsWindow 主窗口
====================================
使用 PyQt6-Fluent-Widgets 的 MSFluentWindow 构建 Win11 原生流畅设计风格设置中心。
负责子页面的组装、导航配置和设置持久化。
"""

import os
import logging

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from qfluentwidgets import (
    MSFluentWindow, FluentIcon,
    InfoBar, InfoBarPosition,
    NavigationItemPosition,
)

from db import DBManager
from utils import static

from settings.llm_page import LLMPage
from settings.chat_page import ChatPage
from settings.voice_page import VoicePage
from settings.visual_page import VisualPage
from settings.cursor_page import CursorPage
from settings.about_page import AboutPage

logger = logging.getLogger(__name__)


class SettingsWindow(MSFluentWindow):
    """MoCli 设置窗口 — Windows 11 原生 Fluent Design 风格"""

    def __init__(self, triangle_cursor=None, llm_engine=None, parent=None):
        super().__init__(parent)
        self.db = DBManager()
        self._triangle_cursor = triangle_cursor
        self.llm_engine = llm_engine

        # 创建子页面
        self.llm_page = LLMPage(self.db, self)

        if self.llm_engine:
            self.chat_page = ChatPage(self.db, self.llm_engine, self)
        else:
            self.chat_page = None

        self.voice_page = VoicePage(self.db, self)
        self.visual_page = VisualPage(self.db, self)
        self.cursor_page = CursorPage(self.db, triangle_cursor, self)
        self.about_page = AboutPage(self)

        self._init_navigation()
        self._init_window()

    def _init_navigation(self):
        """配置侧边栏导航项"""
        self.addSubInterface(self.llm_page, FluentIcon.IOT, "大模型引擎")
        if self.chat_page:
            self.addSubInterface(self.chat_page, FluentIcon.CHAT, "对话")
        self.addSubInterface(self.voice_page, FluentIcon.MICROPHONE, "语音交互")
        self.addSubInterface(self.visual_page, FluentIcon.CAMERA, "视觉感知")
        self.addSubInterface(self.cursor_page, FluentIcon.MOVE, "光标设置")
        self.addSubInterface(self.about_page, FluentIcon.INFO, "关于")

        # 底部：保存按钮
        self.navigationInterface.addItem(
            routeKey='save_action',
            icon=FluentIcon.SAVE,
            text='保存设置',
            onClick=self._save_and_notify,
            position=NavigationItemPosition.BOTTOM
        )

    def _init_window(self):
        """配置窗口属性"""
        self.resize(960, 700)
        self.setMinimumSize(700, 500)
        self.setWindowTitle("MoCli 设置中心")

        # 设置窗口图标
        ico_path = static("mocli-logo.ico")
        png_path = static("mocli-logo-512x512.png")
        if os.path.isfile(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        elif os.path.isfile(png_path):
            self.setWindowIcon(QIcon(png_path))

        # 居中显示
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    def _save_and_notify(self):
        """保存并显示成功提示"""
        self._save()
        InfoBar.success(
            title='已保存',
            content='所有设置已成功保存到数据库',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def closeEvent(self, event):
        """关闭窗口时检查是否有未保存的更改"""
        if hasattr(self.cursor_page, '_cursor_timer'):
            self.cursor_page._cursor_timer.stop()
        self.cursor_page._hide_crosshair()

        # 检查是否有未保存的修改
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "您有未保存的设置更改，是否在关闭前保存？",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
                return
        else:
            event.accept()

        super().closeEvent(event)

    def _has_unsaved_changes(self) -> bool:
        """检查当前 UI 值是否与数据库中已保存的值不同"""
        db = self.db
        checks = [
            db.get("base_url") != self.llm_page.url_input.text().strip(),
            db.get("model") != self.llm_page.model_input.text().strip(),
            db.get("api_key") != self.llm_page.api_key_input.text().strip(),
            db.get_int("memory_size") != self.llm_page.memory_slider.value(),
            db.get("custom_system_prompt", "").strip() != self.llm_page.prompt_edit.toPlainText().strip(),
            db.get("wakeup_keyword") != self.voice_page.keyword_input.text().strip(),
            db.get_bool("wakeup_enabled") != self.voice_page.wakeup_switch.isChecked(),
            db.get_bool("tts_enabled") != self.voice_page.tts_switch.isChecked(),
            db.get("tts_url") != self.voice_page.tts_url_input.text().strip(),
            db.get("tts_model") != self.voice_page.tts_model_input.text().strip(),
            db.get("visual_mode") != self.visual_page.mode_combo.currentData(),
        ]
        return any(checks)

    def _save(self):
        """保存所有配置到数据库"""
        # 大模型设置
        self.db.set("base_url", self.llm_page.url_input.text().strip())
        self.db.set("model", self.llm_page.model_input.text().strip())
        self.db.set("api_key", self.llm_page.api_key_input.text().strip())
        self.db.set("memory_size", str(self.llm_page.memory_slider.value()))
        custom_prompt = self.llm_page.prompt_edit.toPlainText().strip()
        self.db.set("custom_system_prompt", custom_prompt)

        # 唤醒词设置
        self.db.set("wakeup_enabled", str(self.voice_page.wakeup_switch.isChecked()).lower())
        keyword = self.voice_page.keyword_input.text().strip()
        self.db.set("wakeup_keyword", keyword)
        if keyword:
            from wakeup import WakeupEngine
            lines = WakeupEngine.chinese_to_keyword_lines(keyword)
            if lines:
                self.db.set("keyword_lines", "\n".join(lines))

        # TTS 设置
        self.db.set("tts_enabled", str(self.voice_page.tts_switch.isChecked()).lower())
        self.db.set("tts_url", self.voice_page.tts_url_input.text().strip())
        self.db.set("tts_model", self.voice_page.tts_model_input.text().strip())

        # 视觉感知模式
        self.db.set("visual_mode", self.visual_page.mode_combo.currentData())

        # 偏移量
        try:
            self.db.set("offset_x", str(int(self.cursor_page._offset_x.text().strip() or "0")))
            self.db.set("offset_y", str(int(self.cursor_page._offset_y.text().strip() or "0")))
        except ValueError:
            pass

        logger.info("所有设置已保存")
