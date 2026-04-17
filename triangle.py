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

from PyQt6.QtWidgets import QWidget, QLabel, QStyle, QStyleOption, QApplication
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

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态标志
        self.ai_mode = False
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
        self._opacity              = 0.7
        # 各状态颜色（修改此处即可自定义，格式 QColor(R, G, B)）
        self._color_idle           = QColor(40, 44, 52)      # 待机（暗灰）
        self._color_ai             = QColor(0, 200, 255)     # AI 飞行指向（青色）
        self._color_listening      = QColor(0, 220, 100)     # 聆听中（绿色）
        self._color_thinking       = QColor(160, 50, 255)    # 思考推理中（紫色）

        self._init_window()
        self._build_triangle()
        self._init_bubble()
        self._init_animation()
        self._init_timers()

        # 返航颜色渐变进度（0.0=蓝色 → 1.0=灰色，完成后置 None）
        self._color_fade_progress = None
        self._color_fade_timer = QTimer(self)
        self._color_fade_timer.setInterval(30)  # ~33fps
        self._color_fade_timer.timeout.connect(self._tick_color_fade)

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
        # 为了绝对 100% 还原用户最初熟悉的“那个刚刚好的物理大小”：
        # 我们只在启动时获取一次基于主屏幕的 DPR 来下发统一逻辑尺度，不再让它在跨显示器时自行收缩
        screen = QApplication.primaryScreen()
        self._init_dpr = screen.devicePixelRatio() if screen else 1.0
        
        # 抛弃脆弱的自算逻辑，采用绝对的 FixedSize 强制防止多屏穿梭时的高频 move 引发的尺寸崩塌
        self.base_size = int(80 / self._init_dpr)
        self.setFixedSize(self.base_size, self.base_size)

        # 完美还原最初始的画笔缩放计算，但彻底隔离 Qt 系统变量，保持逻辑坐标唯一性
        self._draw_cx = 20.0 / self._init_dpr
        self._draw_cy = 20.0 / self._init_dpr
        self._draw_radius = 11.0 / self._init_dpr

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

    def _init_animation(self):
        """初始化飞行动画引擎：使用 VariantAnimation 以便按帧应用多维变换(位置、旋转、缩放)"""
        from PyQt6.QtCore import QVariantAnimation, QEasingCurve
        self.anim = QVariantAnimation(self)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        # InOutSine 提供极其顺滑的加减速启动和停止
        self.anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.anim.valueChanged.connect(self._on_flight_tick)
        self.anim.finished.connect(self._on_animation_finished)

        # 飞行状态变量
        self._flight_start = QPointF(0, 0)
        self._flight_end = QPointF(0, 0)
        self._flight_control = QPointF(0, 0)
        self._is_animating = False
        # 光标默认在几何形态上有一个 120 度（向下偏右）的主朝向！这里必须是 120.0，否则落地瞬间会抽搐
        self._flight_rotation = 120.0
        self._flight_scale = 1.0

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
        base_radius_scale = 1.0
        flight_rot = 0.0

        # 根据状态切换颜色与形状
        if self.is_listening:
            is_circle = True
            color = self._color_listening
            base_radius_scale = 1.0 + breath * 0.25
        elif self.is_thinking:
            is_circle = True
            color = self._color_thinking
            radius_scale = 1.0 + breath * 0.25
        elif self._color_fade_progress is not None:
            # 返航后颜色渐变：蓝色 → 灰色
            t = self._color_fade_progress
            r = int(self._color_ai.red()   + (self._color_idle.red()   - self._color_ai.red())   * t)
            g = int(self._color_ai.green() + (self._color_idle.green() - self._color_ai.green()) * t)
            b = int(self._color_ai.blue()  + (self._color_idle.blue()  - self._color_ai.blue())  * t)
            color = QColor(r, g, b)
            flight_rot = self._flight_rotation # 渐变期间保持由于返回而产生的朝向
        elif self.ai_mode or self.is_returning:
            color = self._color_ai
            flight_rot = self._flight_rotation
        else:
            color = self._color_idle

        # 获取窗体当前所在屏幕的精确动态 DPI！并交给 QPixmap 接管最终的抗锯齿矩阵缩放
        dpr = self.devicePixelRatioF()
        phys_w = int(self.width() * dpr)
        phys_h = int(self.height() * dpr)
        
        pixmap = QPixmap(phys_w, phys_h)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        pix_painter = QPainter(pixmap)
        pix_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # === 核心仿射变换（应用呼吸、飞行缩放与旋转） ===
        cx = self._draw_cx
        cy = self._draw_cy
        total_scale = base_radius_scale * self._flight_scale
        
        pix_painter.translate(cx, cy)
        # _tri_polygon 默认尖端指向 90度（向下）并预旋转了 20 度 = 120度
        # 当 flight_rot 为方向角时，需减去 120 达到正确的机头指向；为了防止浮点误差导致的不必要旋转使用条件约束
        if abs(flight_rot - 120.0) > 0.1:
            pix_painter.rotate(flight_rot - 120.0)
        if total_scale != 1.0:
            pix_painter.scale(total_scale, total_scale)
        pix_painter.translate(-cx, -cy)
        # ===============================================

        # 非待机状态：先画一层柔和暗色光晕底影，增强在相近色背景上的可见性
        is_active = is_circle or self.ai_mode or self.is_returning or self._color_fade_progress is not None
        if is_active:
            shadow_color = QColor(0, 0, 0, 50)  # 半透明黑色
            shadow_pen = QPen(shadow_color)
            # 这里的巧妙之处：除以 _init_dpr 还原原版粗细，除以 total_scale 抵消 painter 的画布放大引擎，从而做到“身体变大，外轮廓永远保持恒定不粗糙”！
            shadow_pen.setWidthF((9.0 / self._init_dpr) / total_scale)
            shadow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pix_painter.setPen(shadow_pen)
            pix_painter.setBrush(Qt.BrushStyle.NoBrush)
            if is_circle:
                r = self._draw_radius
                pix_painter.drawEllipse(QPointF(cx, cy), r, r)
            else:
                pix_painter.drawPolygon(self._tri_polygon)

        # 主图形绘制
        pen = QPen(color)
        pen.setWidthF((6.0 / self._init_dpr) / total_scale)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pix_painter.setPen(pen)
        
        fill_color = QColor(color)
        if is_circle:
            # 呼吸状态下填充带有透明度变幻的纯色
            fill_color.setAlpha(int(60 + 100 * breath))
        pix_painter.setBrush(fill_color)

        if is_circle:
            r = self._draw_radius
            pix_painter.drawEllipse(QPointF(cx, cy), r, r)
        else:
            pix_painter.drawPolygon(self._tri_polygon)
            
        pix_painter.end()

        # 待机态透明度微呼吸（Δ±0.1，节奏缓慢）
        if not (self.is_listening or self.is_thinking or self.ai_mode or self.is_returning or self._color_fade_progress is not None):
            idle_breath = (math.sin(time.time() * 2) + 1) / 2  # 0~1，周期约 3 秒
            opacity = self._opacity - 0.1 + 0.2 * idle_breath
        else:
            opacity = self._opacity
        painter.setOpacity(opacity)
        painter.drawPixmap(0, 0, pixmap)

    def showEvent(self, event):
        super().showEvent(event)
        _setup_dwm_window(int(self.winId()))
        _setup_dwm_window(int(self.text_label.winId()))

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



    # ==========================================
    # 弹簧物理跟随
    # ==========================================

    def _track_mouse(self):
        """每帧更新三角形位置（弹簧-阻尼物理系统）或触发动画刷新"""
        # 如果处于呼吸动画状态，需要强制每帧重绘（触发 paintEvent 中的 time.time() 获取）
        if self.is_listening or self.is_thinking:
            self.update()

        # >> 平滑回正角度逻辑与连贯动力学 <<
        # 降落完全停稳后（不论是抵达了 AI 目标正在朗读，还是返回了鼠标旁），利用高频跳钟将机头顺滑拉回 120 度的完美静止倾角
        if not getattr(self, '_is_animating', False):
            diff = (120.0 - self._flight_rotation) % 360.0
            if diff > 180.0:
                diff -= 360.0
            if abs(diff) > 0.5:
                # 乘数决定回正阻尼，0.08 提供约 0.5 秒极富惯性质感的缓冲刹车摩擦力（承接那遗留的 120 度动能）
                self._flight_rotation += diff * 0.08  
                self.update()

        if self.ai_mode or getattr(self, 'is_returning', False):
            return

        cursor_pos = self.cursor().pos()
        target_x = cursor_pos.x() + 15
        target_y = cursor_pos.y() + 15

        # 从此处彻底移除了 self.x() 位移断层校验代码
        # 将屏幕穿越的最终权利 100% 移交给下方基于 dt (16ms) 的二阶弹簧模型，拒绝死锁。

        # 二阶弹簧-阻尼系统，参数读自实例属性（可由设置面板动态刷新）
        response = self._spring_response
        damping_fraction = self._damping_fraction
        dt = 0.016  # 帧步长 ≈ 16ms (60 FPS)

        # 转换为离散域的角频率和阻尼系数
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

    def _fly_and_hold(self, px: int, py: int, label: str):
        """飞向目标坐标并无限驻留，不触发自动返回。接收物理像素。"""
        # 气泡显示由 tts.py 的 sync_text 统一驱动，此处不再重复刷新

        # 物理像素 → 逻辑像素
        lx, ly = self._physical_to_logical(px, py)
        
        # 停掉上一轮残留
        self.return_timer.stop()
        self.anim.stop()
        self.hide_timer.stop()
        
        self.ai_mode = True
        self.is_returning = False
        self._is_animating = True

        current = self.pos()
        dist = ((current.x() - lx) ** 2 + (current.y() - ly) ** 2) ** 0.5
        flight_sec = max(0.6, min(1.4, dist / 800.0))
        
        mid_x = (current.x() + lx) / 2.0
        mid_y = (current.y() + ly) / 2.0
        arc_height = min(dist * 0.2, 150.0)

        self._flight_start = QPointF(current.x(), current.y())
        self._flight_end = QPointF(lx, ly)
        self._flight_control = QPointF(mid_x, mid_y - arc_height)

        self.anim.setDuration(int(flight_sec * 1000))
        self.anim.start()

    def ai_move_to(self, x: int, y: int):
        """（已废弃被保留用于向下兼容单点指令）"""
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
        self._is_animating = True

        current = self.pos()
        dist = ((current.x() - x) ** 2 + (current.y() - y) ** 2) ** 0.5
        
        # [动态时长]：越远越久，边界为 0.6s ~ 1.4s
        flight_sec = max(0.6, min(1.4, dist / 800.0))
        fly_ms = int(flight_sec * 1000)

        # [贝塞尔曲线控制点]：起点终点中央，向上抛升（距离的 20%，最大 150 像素高度界限）
        mid_x = (current.x() + x) / 2.0
        mid_y = (current.y() + y) / 2.0
        arc_height = min(dist * 0.2, 150.0)
        
        self._flight_start = QPointF(current.x(), current.y())
        self._flight_end = QPointF(x, y)
        self._flight_control = QPointF(mid_x, mid_y - arc_height)

        self.anim.setDuration(fly_ms)
        self.anim.start()
        self.return_timer.start(fly_ms + dwell_ms)


    def _start_return(self):
        """飞行结束（或等待 TTS 结束）后返回鼠标位置"""
        if self.is_tts_speaking:
            # 如果设定时间到了 TTS 还在读，则挂起，等 TTS 读完再返航
            self.pending_return = True
        else:
            self._do_return()

    def _do_return(self):
        """执行返回动作"""
        self.ai_mode = False
        self.is_returning = True
        self._is_animating = True
        self.pending_return = False
        self._hide_bubble()  # 返回时气泡渐变消失
        
        target = self.cursor().pos()
        tx = target.x() + 15
        ty = target.y() + 15

        current = self.pos()
        dist = ((current.x() - tx) ** 2 + (current.y() - ty) ** 2) ** 0.5
        
        # 归位速度稍快，控制在 0.5s ~ 1.0s
        flight_sec = max(0.5, min(1.0, dist / 800.0))
        duration = int(flight_sec * 1000)

        # 返回同样走贝塞尔曲线
        mid_x = (current.x() + tx) / 2.0
        mid_y = (current.y() + ty) / 2.0
        arc_height = min(dist * 0.2, 100.0)

        self._flight_start = QPointF(current.x(), current.y())
        self._flight_end = QPointF(tx, ty)
        self._flight_control = QPointF(mid_x, mid_y - arc_height)

        self.anim.setDuration(duration)
        self.anim.start()

    def _on_flight_tick(self, t: float):
        """每帧触发：根据 t (0.0 -> 1.0) 计算位置、朝向和缩放并更新"""
        omt = 1.0 - t
        omt2 = omt * omt
        t2 = t * t

        # 1. 贝塞尔抛物线坐标
        bx = omt2 * self._flight_start.x() + 2.0 * omt * t * self._flight_control.x() + t2 * self._flight_end.x()
        by = omt2 * self._flight_start.y() + 2.0 * omt * t * self._flight_control.y() + t2 * self._flight_end.y()

        # 2. 华丽的空翻特技降落（Barrel Roll）并且保留动画余量
        # 空中只完成 240 度的翻滚，剩余的 120 度动能交给它“落地后”的原地惯性刹车去自动宣泄
        spin_t = max(0.0, (t - 0.3) / 0.7)
        # SmoothStep 缓动函数
        smoothed_spin = spin_t * spin_t * (3.0 - 2.0 * spin_t)
        
        # 判断是往屏幕左边飞还是右边飞，以调整顺逆时针的超视距空翻！
        if self._flight_end.x() >= self._flight_start.x():
            self._flight_rotation = 120.0 + smoothed_spin * 240.0
        else:
            self._flight_rotation = 120.0 - smoothed_spin * 240.0

        # 3. 立体缩放感（抛物线顶点最大，起降点恢复1.0，最大放大1.3倍）
        scale_pulse = math.sin(t * math.pi)
        self._flight_scale = 1.0 + scale_pulse * 0.3

        # 设值并激发布局与绘制刷新
        self.move(int(bx), int(by))
        self.update()

    def _on_animation_finished(self):
        self._is_animating = False
        
        # 【关键的断层修复】当飞行降落，动画交接给物理系统的那一刹那，
        # 我们必须把物理系统的底层坐标池与真实的屏幕物理坐标对齐，并归零动量。
        # 否则 `_track_mouse` 恢复运行的第一帧，会拿取之前留在原地的落后坐标来强行驱动弹簧，从而导致闪烁回拉残影！
        self.actual_x = float(self.x())
        self.actual_y = float(self.y())
        self.vel_x = 0.0
        self.vel_y = 0.0
        
        if self.is_returning:
            self.is_returning = False
            self._flight_scale = 1.0
            # 启动颜色渐变：蓝色 → 灰色（1 秒过渡），保留最后滞留的方向角直到融合完毕
            self._color_fade_progress = 0.0
            self._color_fade_timer.start()
        elif self.ai_mode:
            # 停稳后恢复大小，但绝不瞬间清零角度！通过 _track_mouse 接管并平滑回正
            self._flight_scale = 1.0
            self.update()

    def _tick_color_fade(self):
        """颜色渐变定时器回调：30ms 一帧，1 秒完成"""
        if self._color_fade_progress is None:
            self._color_fade_timer.stop()
            return
        self._color_fade_progress += 0.03  # ~33 帧 × 0.03 ≈ 1.0
        if self._color_fade_progress >= 1.0:
            self._color_fade_progress = None
            self._color_fade_timer.stop()
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
