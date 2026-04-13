# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
utils.py - MoCli 共享工具函数
================================
职责：
  - 资源文件路径解析（static/ 目录）
  - SVG → QIcon 渲染
  - DPI 缩放工具
"""

import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QIcon


# 项目根目录（utils.py 所在目录）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 静态资源目录
_STATIC_DIR = os.path.join(_BASE_DIR, "static")


def res(filename: str) -> str:
    """获取与项目根目录中的资源文件绝对路径"""
    return os.path.join(_BASE_DIR, filename)


def static(filename: str) -> str:
    """获取 static/ 目录下资源文件的绝对路径"""
    return os.path.join(_STATIC_DIR, filename)


def icon_from_svg(svg_path: str, size: int = 22) -> QIcon:
    """将 SVG 文件渲染为指定尺寸的 QIcon"""
    if not os.path.isfile(svg_path):
        return QIcon()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    # 通过 QSvgRenderer 渲染 SVG
    from PyQt6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(svg_path)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def scale(value: int) -> int:
    """根据系统 DPI 缩放像素值，确保 Win11 高 DPI 下显示正常"""
    screen = QApplication.primaryScreen()
    if screen:
        ratio = screen.devicePixelRatio()
        return int(value * max(1.0, ratio * 0.75))
    return value
