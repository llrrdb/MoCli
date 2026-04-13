# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
triangle.py - MoCli 三角形光标 UI
=====================================
包含：
  - 三角形几何构建与渲染
  - 弹簧-阻尼物理跟随系统
  - AI 指向飞行动画
  - 文字气泡与输入框交互
  - Windows DWM 窗口优化
"""

import math
import time
import ctypes
import ctypes.wintypes

from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QStyle, QStyleOption, QApplication
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QPoint, QPointF
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics,
    QPen, QPolygonF, QPixmap
)


def _setup_dwm_window(hwnd: int):
    """通过 DwmSetWindowAttribute 消除 Windows DWM 的圆角和阴影"""
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        hwnd_c = ctypes.wintypes.HWND(hwnd)

        # 禁用 Win11 圆角
        DWMWA_WINDOW_CORNER_PREFERENCE = ctypes.c_uint(33)
        corner_val = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd_c, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_val), ctypes.sizeof(corner_val)
        )

        # 禁用 NC 渲染（阴影）
        DWMWA_NCRENDERING_POLICY = ctypes.c_uint(2)
        nc_val = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            hwnd_c, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(nc_val), ctypes.sizeof(nc_val)
        )
    except Exception:
        pass


class BubbleLabel(QLabel):
    """
    重写 QLabel，修复作为独立 Translucent 顶层窗口时 CSS 背景不渲染的问题
    """
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        super().paintEvent(event)


class TriangleCursor(QWidget):
    """
    MoCli 三角形光标组件。
    包含弹簧物理跟随、飞行动画、气泡显示和文本输入功能。
    """

    # 用户通过键盘输入框提交文字时发射
    input_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态标志
        self.ai_mode = False
        self.is_typing = False
        self.is_returning = False
        self.is_listening = False
        self.is_thinking = False

        # 弹簧物理系统
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.actual_x = 0.0
        self.actual_y = 0.0

        # ─── 光标外观参数（硬编码，修改后重启程序生效） ───
        # 弹簧自然周期（秒）：越小越灵敏紧跟（0.15 极紧 | 0.3 灵敏 | 0.5 平衡 | 0.8 慢悠）
        self._spring_response      = 0.4
        # 阻尼比：< 1 有弹性回弹（0.4 弹跃感 | 0.6 平衡 | 1.0 无回弹临界阻尼）
        self._damping_fraction     = 0.6
        # 整体透明度（0.0 全透明 ~ 1.0 不透明）
        self._opacity              = 0.9
        # 各状态颜色（修改此处即可自定义，格式 QColor(R, G, B)）
        self._color_idle           = QColor(40, 44, 52)      # 待机（暗灰）
        self._color_ai             = QColor(0, 200, 255)     # AI 飞行指向（青色）
        self._color_typing         = QColor(255, 170, 0)     # 文本输入中（橙色）
        self._color_listening      = QColor(0, 220, 100)     # 聆听中（绿色）
        self._color_thinking       = QColor(160, 50, 255)    # 思考推理中（紫色）

        self._init_window()
        self._build_triangle()
        self._init_bubble()
        self._init_input_box()
        self._init_animation()
        self._init_timers()

    # ==========================================
    # 初始化
    # ==========================================

    def _init_window(self):
        """设置窗口属性：无边框、置顶、透明、鼠标穿透"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # 在 HiDPI 下将逻辑尺寸除以 DPR，保持光标物理尺寸不变
        screen = QApplication.primaryScreen()
        self._dpr = screen.devicePixelRatio() if screen else 1.0
        self.base_size = int(80 / self._dpr)
        self.resize(self.base_size, self.base_size)

        # 缩放后的绘制中心和半径（适配缩放后的 widget 大小）
        self._draw_cx = 20 / self._dpr
        self._draw_cy = 20 / self._dpr
        self._draw_radius = 11 / self._dpr

    def _build_triangle(self):
        """构建等边三角形的顶点坐标（正旋转 20°）"""
        cx = self._draw_cx
        cy = self._draw_cy
        radius = self._draw_radius
        rotation = 20

        self._tri_points = []
        for angle in [210, 330, 90]:
            rad = math.radians(angle + rotation)
            px = cx + radius * math.cos(rad)
            py = cy + radius * math.sin(rad)
            self._tri_points.append(QPointF(px, py))
        self._tri_polygon = QPolygonF(self._tri_points)

    def _init_bubble(self):
        """初始化文字气泡"""
        self.text_label = BubbleLabel("MoCli 已就绪", self)
        # 将其设置为独立的 ToolTip 窗口，不受父窗口边界裁剪
        self.text_label.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # 字体加粗（Light -> Medium）
        self.text_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Medium))
        self.text_label.setStyleSheet("""
            color: #E0E0E0;
            background-color: rgba(40, 44, 52, 220);
            border-radius: 8px;
            padding: 10px;
        """)
        self.text_label.setWordWrap(True)
        self.text_label.setWindowOpacity(0.0)
        self.text_label.hide()
        
        # 气泡渐显动画
        self.fade_in_anim = QPropertyAnimation(self.text_label, b"windowOpacity", self)
        self.fade_in_anim.setDuration(500)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(1.0)
        
        # 气泡渐隐动画
        self.fade_out_anim = QPropertyAnimation(self.text_label, b"windowOpacity", self)
        self.fade_out_anim.setDuration(500)
        # EndValue 始终为 0.0，并在完成时真隐藏
        self.fade_out_anim.setEndValue(0.0)
        self.fade_out_anim.finished.connect(self.text_label.hide)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_bubble)
        self.pending_hide = False

    def _init_input_box(self):
        """初始化文本输入框"""
        self.input_box = QLineEdit(self)
        self.input_box.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.input_box.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 输入框字体加粗（Light -> Medium）
        self.input_box.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Medium))
        self.input_box.setPlaceholderText("在此输入指令...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                color: #FFFFFF;
                background-color: rgba(30, 33, 39, 240);
                border: 2px solid #00C8FF;
                border-radius: 8px;
                padding: 5px 10px;
            }
        """)
        self.input_box.hide()
        self.input_box.returnPressed.connect(self._submit_input)
        self.input_box.textChanged.connect(self._adjust_input_size)

    def _init_animation(self):
        """初始化飞行动画引擎"""
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.finished.connect(self._on_animation_finished)

    def _init_timers(self):
        """初始化鼠标追踪和返回定时器"""
        self.is_tts_speaking = False
        self.pending_return = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._track_mouse)
        self.timer.start(16)

        self.return_timer = QTimer(self)
        self.return_timer.setSingleShot(True)
        self.return_timer.timeout.connect(self._start_return)

    # ==========================================
    # 渲染
    # ==========================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取呼吸缩放系数 (0.0 to 1.0)
        breath = (math.sin(time.time() * 6) + 1) / 2
        is_circle = False
        radius_scale = 1.0

        # 根据状态切换颜色与形状
        if self.is_listening:
            is_circle = True
            color = self._color_listening
            radius_scale = 1.0 + breath * 0.25
        elif self.is_thinking:
            is_circle = True
            color = self._color_thinking
            radius_scale = 1.0 + breath * 0.25
        elif self.ai_mode or self.is_returning:
            color = self._color_ai
        elif self.is_typing:
            color = self._color_typing
        else:
            color = self._color_idle

        # 使用高分辨率 QPixmap 消除 HiDPI 锯齿
        dpr = self._dpr
        phys_w = int(self.width() * dpr)
        phys_h = int(self.height() * dpr)
        pixmap = QPixmap(phys_w, phys_h)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        pix_painter = QPainter(pixmap)
        pix_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(color)
        pen.setWidthF(6.0 / dpr)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pix_painter.setPen(pen)
        
        fill_color = QColor(color)
        if is_circle:
            # 呼吸状态下填充带有透明度变幻的纯色
            fill_color.setAlpha(int(60 + 100 * breath))
        pix_painter.setBrush(fill_color)

        if is_circle:
            cx = self._draw_cx
            cy = self._draw_cy
            r = self._draw_radius * radius_scale
            pix_painter.drawEllipse(QPointF(cx, cy), r, r)
        else:
            pix_painter.drawPolygon(self._tri_polygon)
            
        pix_painter.end()

        painter.setOpacity(self._opacity)
        painter.drawPixmap(0, 0, pixmap)

    def showEvent(self, event):
        super().showEvent(event)
        _setup_dwm_window(int(self.winId()))
        _setup_dwm_window(int(self.text_label.winId()))
        _setup_dwm_window(int(self.input_box.winId()))

    def moveEvent(self, event):
        """主窗口移动时，同步更新独立气泡的绝对坐标，防止超出屏幕"""
        super().moveEvent(event)
        self._sync_overlays()

    def _sync_overlays(self):
        """同步气泡/输入框位置，X/Y 轴简单 clamp 到屏幕边缘，不做翻转"""
        from PyQt6.QtWidgets import QApplication
        screen = self.screen()
        if not screen:
            screen = QApplication.primaryScreen()
        if not screen:
            return

        sg = screen.geometry()

        def _move_clamped(widget):
            if not widget.isHidden():
                bw, bh = widget.width(), widget.height()

                # 期望位置：光标右下方，Y 轴留出安全距离避免遮挡三角形
                tx = self.x() + 40
                ty = self.y() + 35

                # 简单 clamp：超出屏幕右边界就停住，不翻转
                tx = min(tx, sg.right() - bw - 10)
                tx = max(sg.left() + 10, tx)

                # 简单 clamp：超出屏幕下边界就停住，不翻转
                ty = min(ty, sg.bottom() - bh - 10)
                ty = max(sg.top() + 10, ty)

                widget.move(int(tx), int(ty))

        _move_clamped(self.text_label)
        _move_clamped(self.input_box)



    # ==========================================
    # 弹簧物理跟随
    # ==========================================

    def _track_mouse(self):
        """每帧更新三角形位置（弹簧-阻尼物理系统）或触发动画刷新"""
        # 如果处于呼吸动画状态，需要强制每帧重绘（触发 paintEvent 中的 time.time() 获取）
        if self.is_listening or self.is_thinking:
            self.update()

        if self.ai_mode or self.is_typing or self.is_returning:
            return

        cursor_pos = self.cursor().pos()
        target_x = cursor_pos.x() + 15
        target_y = cursor_pos.y() + 15

        # 检测位移断层，同步状态
        if abs(self.x() - self.actual_x) > 10 or abs(self.y() - self.actual_y) > 10:
            self.actual_x = float(self.x())
            self.actual_y = float(self.y())
            self.vel_x = 0.0
            self.vel_y = 0.0

        # 二阶弹簧-阻尼系统，参数读自实例属性（可由设置面板动态刷新）
        response = self._spring_response
        damping_fraction = self._damping_fraction
        dt = 0.016  # 帧步长 ≈ 16ms (60 FPS)

        # 将 SwiftUI 参数转换为离散域的角频率和阻尼系数
        omega_n = 2.0 * math.pi / response          # 自然角频率
        k = omega_n * omega_n                        # 弹簧刚度 (ω²)
        c = 2.0 * damping_fraction * omega_n         # 阻尼系数 (2ζω)

        # 半隐式欧拉积分（先更新速度，再更新位置，能量稳定）
        accel_x = (target_x - self.actual_x) * k - self.vel_x * c
        accel_y = (target_y - self.actual_y) * k - self.vel_y * c

        self.vel_x += accel_x * dt
        self.vel_y += accel_y * dt
        self.actual_x += self.vel_x * dt
        self.actual_y += self.vel_y * dt

        # 死区防抖：速度和距离都极小时强制归零
        if abs(self.vel_x) < 0.5 and abs(target_x - self.actual_x) < 0.5:
            self.actual_x = float(target_x)
            self.vel_x = 0.0
        if abs(self.vel_y) < 0.5 and abs(target_y - self.actual_y) < 0.5:
            self.actual_y = float(target_y)
            self.vel_y = 0.0

        self.move(int(self.actual_x), int(self.actual_y))

    # ==========================================
    # 飞行动画
    # ==========================================

    def ai_move_to(self, x: int, y: int):
        """让三角形飞向指定屏幕坐标（接收物理像素，自动转换为逻辑像素）"""
        lx, ly = self._physical_to_logical(x, y)
        self._fly_to(lx, ly, dwell_ms=4000)

    def test_move_to(self, x: int, y: int, duration_sec: int = 15):
        """测试用：飞向指定坐标并停留 duration_sec 秒后自动返回（接收物理像素）"""
        lx, ly = self._physical_to_logical(x, y)
        self._fly_to(lx, ly, dwell_ms=duration_sec * 1000)

    @staticmethod
    def _physical_to_logical(px: int, py: int) -> tuple:
        """物理像素 → Qt 逻辑像素（高 DPI 屏幕下需要除以 devicePixelRatio）"""
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
        return int(px / ratio), int(py / ratio)

    def _fly_to(self, x: int, y: int, dwell_ms: int):
        """通用飞行逻辑：启动动画 + 设置 dwell_ms 后返回的定时器"""
        self.return_timer.stop()
        self.anim.stop()
        
        # 同步气泡：若在飞行，则取消气泡自身的隐藏定时器，让气泡的命运完全同返回定时器挂钩！
        self.hide_timer.stop()
        
        self.ai_mode = True
        self.is_returning = False

        current = self.pos()
        dist = ((current.x() - x) ** 2 + (current.y() - y) ** 2) ** 0.5
        fly_ms = int(max(400, min(1200, dist * 0.7)))

        self.anim.setDuration(fly_ms)
        self.anim.setStartValue(current)
        self.anim.setEndValue(QPoint(x, y))
        self.anim.start()
        self.return_timer.start(fly_ms + dwell_ms)


    def _start_return(self):
        """飞行结束（或等待 TTS 结束）后返回鼠标位置"""
        if self.is_typing:
            self.ai_mode = False
            return

        if self.is_tts_speaking:
            # 如果设定时间到了 TTS 还在读，则挂起，等 TTS 读完再返航
            self.pending_return = True
        else:
            self._do_return()

    def _do_return(self):
        """执行返回动作"""
        self.ai_mode = False
        self.is_returning = True
        self.pending_return = False
        self._hide_bubble()  # 返回时气泡渐变消失
        
        target = self.cursor().pos()
        tx, ty = target.x() + 15, target.y() + 15

        current = self.pos()
        dist = ((current.x() - tx) ** 2 + (current.y() - ty) ** 2) ** 0.5
        duration = int(max(300, min(1000, dist * 0.6)))

        self.anim.setDuration(duration)
        self.anim.setStartValue(current)
        self.anim.setEndValue(QPoint(tx, ty))
        self.anim.start()

    def _on_animation_finished(self):
        if self.is_returning:
            self.is_returning = False
            self.update()

    def on_tts_state_changed(self, is_speaking: bool):
        """TTS 状态变更回调：如果从说话变为停下，且堆积了返回指令，则立即返航"""
        self.is_tts_speaking = is_speaking
        if not is_speaking:
            if self.pending_return:
                self._do_return()
            elif self.pending_hide:
                self.pending_hide = False
                self._hide_bubble()

    def set_action_state(self, state: str):
        """
        设置光标的交互状态以切换外形和颜色。
        state: 'idle', 'listening' (听语气), 'thinking' (加载思考)
        """
        if state == "listening":
            self.is_listening = True
            self.is_thinking = False
        elif state == "thinking":
            self.is_listening = False
            self.is_thinking = True
        else:
            self.is_listening = False
            self.is_thinking = False
        self.update()

    # ==========================================
    # 气泡显示
    # ==========================================

    def display_text(self, text: str):
        """在三角形旁显示文字气泡"""
        if not text.strip():
            text = "执行完毕"
        self.text_label.setText(text)

        fm = QFontMetrics(self.text_label.font())
        max_w = 400
        rect = fm.boundingRect(0, 0, max_w, 2000, Qt.TextFlag.TextWordWrap, text)
        bw = rect.width() + 30
        bh = rect.height() + 20
        self.text_label.setFixedSize(bw, bh)
        self.fade_out_anim.stop()
        
        # 触发渐显
        if self.text_label.isHidden() or self.text_label.windowOpacity() == 0:
            self.text_label.setWindowOpacity(0.0)
            self.text_label.show()
            self.fade_in_anim.setStartValue(0.0)
            self.fade_in_anim.setEndValue(1.0)
            self.fade_in_anim.start()
        else:
            self.fade_in_anim.stop()
            self.text_label.setWindowOpacity(1.0)

        # 更新对齐
        self._sync_overlays()

        self.hide_timer.stop()
        self.pending_hide = False
        # 非飞行时，默认气泡驻留 8 秒
        self.hide_timer.start(8000)

    def _hide_bubble(self):
        if self.is_tts_speaking:
            self.pending_hide = True
            return
            
        if not self.text_label.isHidden():
            self.fade_in_anim.stop()
            self.fade_out_anim.setStartValue(self.text_label.windowOpacity())
            self.fade_out_anim.start()

    # ==========================================
    # 文本输入框
    # ==========================================

    def prepare_input(self):
        """弹出文本输入框（由 Ctrl+M 触发）"""
        self.is_typing = True
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide_timer.stop()
        self.text_label.hide()
        self.input_box.clear()
        self._adjust_input_size()
        self.input_box.show()
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(50, self.input_box.setFocus)
        self.update()

    def _submit_input(self):
        """提交输入框内容"""
        text = self.input_box.text().strip()
        self.input_box.hide()
        self.is_typing = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if text:
            self.input_submitted.emit(text)

    def _adjust_input_size(self):
        text = self.input_box.text()
        fm = QFontMetrics(self.input_box.font())
        text_w = fm.horizontalAdvance(text) + 50
        new_w = max(250, min(text_w, 800))
        self.input_box.resize(new_w, 36)
        # 更新对齐
        self._sync_overlays()
