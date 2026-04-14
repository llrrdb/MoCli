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
    截取主屏幕并进行强力压缩，返回 (base64_str, raw_width, raw_height)。
    返回的宽高始终是屏幕的原始物理分辨率，以确保 AI 坐标换算准确无误。

    【核心优化】
    1. 等比例缩放（Downsample）：无论原始屏幕多大（如 4K 或视网膜屏），均将图像比例缩小至最大宽度 1280。
    2. JPEG 强压缩：使用 quality=80 压缩参数。
    效果：将动辄 5~10MB 的视网膜屏幕截图暴降至百 KB 级别，上行发送到云端时间微乎其微，同时极大节省了 Token 开销。
    """
    screen = ImageGrab.grab()
    raw_width, raw_height = screen.size

    # 计算目标缩放尺寸（设定最高宽度阈值为 1280）
    MAX_WIDTH = 1280
    if raw_width > MAX_WIDTH:
        # 等比例缩放计算，保持宽高比
        ratio = MAX_WIDTH / raw_width
        target_width = MAX_WIDTH
        target_height = int(raw_height * ratio)

        try:
            # Pillow 10+ 推荐使用 Image.Resampling.LANCZOS
            from PIL import Image
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            # 兼容老版本 Pillow
            from PIL import Image
            resample_filter = Image.LANCZOS

        # 进行高质量缩放抗锯齿处理
        resized_screen = screen.resize((target_width, target_height), resample_filter)
    else:
        resized_screen = screen

    # 编码为 JPEG Base64（quality=80 是压缩比与清晰度的最佳实战平衡）
    buffered = io.BytesIO()
    resized_screen.save(buffered, format="JPEG", quality=80)
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return img_base64, raw_width, raw_height


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
