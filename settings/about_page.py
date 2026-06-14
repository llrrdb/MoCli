# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
about_page.py - 关于页面
===========================
显示免责声明等 Markdown 渲染内容。
使用 SettingCardGroup 包裹，Fluent Design 风格。
"""

import os

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    SettingCardGroup, FluentIcon,
    ScrollArea,
)

from utils import static


class AboutPage(ScrollArea):
    """关于页面——显示免责声明等信息"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutPage")
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
        # 分组标题
        group = SettingCardGroup("关于 MoCli", self)
        self.lay.addWidget(group)

        # 内容浏览器
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet("""
            QTextBrowser {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 8px;
                padding: 24px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)

        md_path = static("免责声明.md")
        if os.path.isfile(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            html = self._render_markdown(md_text)
            self._browser.setHtml(html)
        else:
            self._browser.setPlainText("未找到免责声明文件。")

        self.lay.addWidget(self._browser)
        self.lay.addStretch()

    @staticmethod
    def _render_markdown(md_text: str) -> str:
        import markdown as md_lib
        body = md_lib.markdown(md_text, extensions=["extra"])
        return f"""
        <style>
            body {{ font-family: 'Microsoft YaHei UI', sans-serif; color: #333; }}
            h1, h2, h3, h4 {{ color: #1a1a2e; }}
            h2 {{ border-bottom: 1px solid #eee; padding-bottom: 6px; }}
            blockquote {{
                border-left: 3px solid #005FB8;
                padding: 8px 16px; margin: 12px 0;
                color: #555; background: #F5F5F5;
            }}
            hr {{ border: none; border-top: 1px solid #ddd; margin: 16px 0; }}
            a {{ color: #005FB8; text-decoration: none; }}
            p {{ line-height: 1.7; margin: 6px 0; }}
        </style>
        {body}
        """
