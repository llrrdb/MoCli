# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
main.py - MoCli 主程序入口
============================
职责：
  1. 配置日志系统
  2. 配置 Qt 高 DPI 缩放策略
  3. 设置 Windows AppUserModelID（任务栏图标）
  4. 创建 QApplication 和全局字体
  5. 实例化所有子模块并连接信号
  6. 注册全局热键
"""

import os

# 在任何第三方库加载前，注入高版本 ONNX 引擎路径
try:
    import onnxruntime
    if hasattr(os, 'add_dll_directory'):
        capi_dir = os.path.join(os.path.dirname(onnxruntime.__file__), "capi")
        os.add_dll_directory(capi_dir)
except Exception:
    pass

import sys
import time
import logging
import threading

import ctypes

import keyboard

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from db import DBManager
from settings import SettingsWindow
from tray import create_tray
from triangle import TriangleCursor
from llm import LLMEngine
from voice import VoiceManager, VoiceSignals, AppSignals


# ==========================================
# 日志配置
# ==========================================
def _setup_logging():
    """配置全局日志格式和级别"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(name)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger(__name__)


# ==========================================
# MoCli 应用主类
# ==========================================
class MoCli:
    """MoCli 应用：负责实例化所有模块并连接信号"""

    def __init__(self):
        self.db = DBManager()
        self.llm = LLMEngine(self.db)

        # 并发锁（在 __init__ 中初始化，避免延迟初始化竞态）
        self._ai_lock = threading.Lock()
        self._last_ptt_time = 0.0  # F10 防抖时间戳

        # UI 组件
        self.cursor = TriangleCursor()

        # 系统托盘（预创建，零延迟）
        self.tray, settings_act, quit_act = create_tray(self.cursor)
        settings_act.triggered.connect(self._open_settings)
        quit_act.triggered.connect(QApplication.instance().quit)
        self.tray.activated.connect(self._on_tray_activated)

        # AI 后台线程 → 主线程 信号桥（解决跨线程 UI 死锁）
        self.app_signals = AppSignals()
        self.app_signals.update_text.connect(self.cursor.display_text)
        self.app_signals.move_to.connect(self.cursor.ai_move_to)
        self.app_signals.request_tts.connect(
            lambda text: self.voice_mgr.request_tts(text)
        )
        self.app_signals.set_action_state.connect(self.cursor.set_action_state)

        # 语音管理器
        self.voice_signals = VoiceSignals()
        self.voice_mgr = VoiceManager(self.db, self.voice_signals)

        # 连接所有信号
        self._connect_signals()

        # 显示三角形
        self.cursor.show()

        # 延迟启动语音引擎
        self.voice_mgr.start()

        # 注册 F10 一键唤起麦克风 (PTT)
        keyboard.add_hotkey('f10', self._on_ptt)

        logger.info("MoCli 初始化完成")

    def _connect_signals(self):
        """连接所有跨模块信号"""
        # 键盘输入 → AI
        self.cursor.input_submitted.connect(self._on_user_input)

        # 语音输入 → AI
        self.voice_signals.stt_result.connect(self._on_user_input)

        # 语音信息状态提示 → 气泡
        self.voice_signals.status_update.connect(self._on_voice_status)

        # 唤醒成功 → UI 呼吸
        self.voice_signals.wakeup_detected.connect(
            lambda: self.cursor.set_action_state("listening")
        )

        # TTS 正在说话状态 → 光标悬停防返回
        self.voice_signals.tts_state_changed.connect(self.cursor.on_tts_state_changed)

    def _on_user_input(self, text: str):
        """统一处理用户输入（键盘/语音皆走此通道），带并发锁防止重复请求"""
        if not self._ai_lock.acquire(blocking=False):
            # 已有请求在执行中，丢弃本次输入
            logger.info("上一个请求尚未完成，忽略输入: %s...", text[:30])
            self.cursor.display_text("正在处理上一个请求...")
            return

        self.cursor.display_text("正在扫描屏幕...")
        self.cursor.set_action_state("thinking")
        # 在后台线程中执行 AI 请求
        thread = threading.Thread(target=self._ask_ai, args=(text,), daemon=True)
        thread.start()

    def _ask_ai(self, text: str):
        """后台线程：执行完整的 AI 请求流程（通过信号安全更新 UI）"""
        try:
            result = self.llm.ask(text)

            # 恢复空闲状态
            self.app_signals.set_action_state.emit("idle")

            if result["error"]:
                self.app_signals.update_text.emit(f"错误: {result['error']}")
                return

            # 组合带有目标 Label 的富文本显示
            display = result["spoken_text"] or "完成"

            # 飞向目标坐标（同时组合标题显示）
            if result["point"]:
                px, py, label = result["point"]
                # 如果有目标，则将目标作为头部强调标题，并加入一条视觉分割线
                display = f"{label}\n──────────────\n{display}"
                self.app_signals.move_to.emit(px, py)

            # 更新合并后的 UI 气泡
            self.app_signals.update_text.emit(display)

            # TTS 朗读
            if result["spoken_text"]:
                self.app_signals.request_tts.emit(result["spoken_text"])
        except Exception as e:
            logger.error("AI 请求异常: %s", e, exc_info=True)
            self.app_signals.set_action_state.emit("idle")
            self.app_signals.update_text.emit(f"错误: {str(e)[:60]}")
        finally:
            # 无论成功还是异常，都必须释放锁，否则后续请求永远被阻塞
            self._ai_lock.release()

    def _on_voice_status(self, text: str):
        """语音引擎状态提示"""
        if text:
            self.cursor.display_text(text)
        else:
            self.cursor._hide_bubble()
            self.cursor.set_action_state("idle")

    def _on_ptt(self):
        """
        F10 智能触发：开始录音 / 结束录音 / AI 处理中忽略。
        内置 500ms 防抖，防止 keyboard 库发送重复事件。
        """
        # AI 正在处理中，阻止一切新触发
        if self._ai_lock.locked():
            logger.debug("AI 正在处理中，忽略 F10")
            return
        # 防抖：500ms 内不接受重复触发
        now = time.time()
        if now - self._last_ptt_time < 0.5:
            return
        self._last_ptt_time = now
        self.voice_mgr.trigger_ptt()

    def _on_tray_activated(self, reason):
        """托盘图标双击时打开设置"""
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_settings()

    def _open_settings(self):
        """打开设置窗口（MSFluentWindow 风格）"""
        # 复用已打开的窗口（防止重复创建）
        if hasattr(self, '_settings_win') and self._settings_win is not None:
            self._settings_win.raise_()
            self._settings_win.activateWindow()
            return
        self._settings_win = SettingsWindow(triangle_cursor=self.cursor)
        self._settings_win.destroyed.connect(lambda: setattr(self, '_settings_win', None))
        self._settings_win.show()


# ==========================================
# 程序入口
# ==========================================
if __name__ == '__main__':
    _setup_logging()

    # 设置 Windows AppUserModelID（让任务栏显示自定义图标而非 Python 默认图标）
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.shumox.mocli")
    except Exception:
        pass

    # 允许 Qt 使用精确的缩放因子（不取整），确保高 DPI 屏幕渲染清晰
    from PyQt6.QtCore import Qt as QtConst
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        QtConst.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 全局字体：细字重
    font = QFont("Microsoft YaHei UI")
    font.setWeight(QFont.Weight.Light)
    app.setFont(font)

    mocli = MoCli()
    sys.exit(app.exec())
