# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
tray.py - MoCli 系统托盘
================================
职责：
  - 创建系统托盘图标和右键菜单
  - Win11 Fluent Design 风格菜单样式
"""

import os
import math
import logging

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QPolygonF,
    QPixmap, QIcon, QAction
)

from utils import static, icon_from_svg

logger = logging.getLogger(__name__)


# 托盘菜单样式
TRAY_MENU_STYLE = """
    QMenu {
        background: rgba(249, 249, 249, 0.98);
        border: 1px solid #D9D9D9;
        border-radius: 10px;
        padding: 6px;
        font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
        font-size: 16px;
    }
    QMenu::item {
        color: #1A1A1A;
        padding: 9px 28px 9px 12px;
        border-radius: 5px;
        margin: 2px 4px;
    }
    QMenu::item:selected {
        background: rgba(0, 0, 0, 0.06);
    }
    QMenu::item:disabled {
        color: #8A8A8A;
    }
    QMenu::separator {
        height: 1px;
        background: #D9D9D9;
        margin: 4px 10px;
    }
"""


def create_tray(parent) -> tuple:
    """
    创建系统托盘图标和右键菜单。
    返回 (QSystemTrayIcon, settings_action, quit_action)。
    """
    tray = QSystemTrayIcon(parent)

    # 托盘图标：优先使用 ICO 文件（Win 系统兼容性最佳）
    ico_path = static("mocli-logo.ico")
    png_path = static("mocli-logo-512x512.png")
    if os.path.isfile(ico_path):
        tray_icon = QIcon(ico_path)
    elif os.path.isfile(png_path):
        tray_icon = QIcon(png_path)
    else:
        # Fallback：代码绘制三角形图标
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pts = []
        for a in [210, 330, 90]:
            r = math.radians(a + 20)
            pts.append(QPointF(32 + 18 * math.cos(r), 32 + 18 * math.sin(r)))
        pen = QPen(QColor(0, 200, 255))
        pen.setWidth(7)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QColor(0, 200, 255, 60))
        p.drawPolygon(QPolygonF(pts))
        p.end()
        tray_icon = QIcon(pix)

    tray.setIcon(tray_icon)
    tray.setToolTip("MoCli AI Assistant  ·  运行中")

    # 绘制菜单图标
    def _make_icon(svg_name: str) -> QIcon:
        return icon_from_svg(static(svg_name), 20)

    menu = QMenu()
    menu.setStyleSheet(TRAY_MENU_STYLE)

    # 状态提示（只读）
    status_action = QAction("● MoCli 正在运行", parent)
    status_action.setEnabled(False)

    # 设置中心
    settings_action = QAction("  设置中心", parent)
    settings_action.setIcon(_make_icon("设置中心.svg"))

    # 退出
    quit_action = QAction("  退出程序", parent)
    quit_action.setIcon(_make_icon("退出.svg"))

    menu.addAction(status_action)
    menu.addSeparator()
    menu.addAction(settings_action)
    menu.addSeparator()
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()

    logger.info("系统托盘已创建")
    return tray, settings_action, quit_action
