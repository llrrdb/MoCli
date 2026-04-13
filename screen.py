# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
screen.py - MoCli 屏幕截图工具
================================
提供无损物理像素截图与 Base64 编码功能。
"""

import io
import base64
import ctypes
import logging

from PIL import ImageGrab

logger = logging.getLogger(__name__)


def capture_screen() -> tuple:
    """
    截取主屏幕，返回 (base64_str, width, height)。
    图像为原生物理分辨率（如 2560x1600），无任何缩放。
    """
    screen = ImageGrab.grab()
    width, height = screen.size

    # 编码为 JPEG Base64（quality=85 是质量与体积的最佳平衡点）
    buffered = io.BytesIO()
    screen.save(buffered, format="JPEG", quality=85)
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return img_base64, width, height


def get_screen_size() -> tuple:
    """
    轻量级获取屏幕物理分辨率（不截图，通过 Win32 API 直接查询）。
    返回 (width, height)。
    """
    try:
        user32 = ctypes.windll.user32
        # 设置 DPI 感知以获取真实物理分辨率
        user32.SetProcessDPIAware()
        width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return width, height
    except Exception:
        # Fallback：使用 PIL 截图方式（兼容性保底）
        logger.warning("Win32 API 获取分辨率失败，回退到 PIL 方式")
        screen = ImageGrab.grab()
        w, h = screen.size
        screen.close()
        return w, h
