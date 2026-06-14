# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
cursor_page.py - 光标设置页面
================================
包含实时光标坐标监控、定点飞行测试、全局偏移量校准和屏幕中心准星。
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor

from qfluentwidgets import (
    SubtitleLabel, BodyLabel,
    LineEdit, PrimaryPushButton, PushButton,
    ScrollArea,
)

from db import DBManager
from settings.cards import FluentCard

logger = logging.getLogger(__name__)


# ==========================================
# 屏幕中心准星覆盖层
# ==========================================

class CrosshairOverlay(QWidget):
    """屏幕物理中心准星——用于校准光标定位精度"""

    def __init__(self, phys_cx: int, phys_cy: int, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._phys_cx = phys_cx
        self._phys_cy = phys_cy

        # 逻辑像素尺寸
        size = 200
        self.resize(size, size)

        # 物理中心 → 逻辑中心（用于 Qt 定位）
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
        logical_cx = int(phys_cx / ratio)
        logical_cy = int(phys_cy / ratio)
        self.move(logical_cx - size // 2, logical_cy - size // 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() // 2
        cy = self.height() // 2

        pen = QPen(QColor(255, 50, 50), 2)
        p.setPen(pen)

        # 十字线（中间留空）
        gap, arm = 8, 50
        p.drawLine(cx - arm, cy, cx - gap, cy)
        p.drawLine(cx + gap, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy - gap)
        p.drawLine(cx, cy + gap, cx, cy + arm)

        # 外圆环
        r = 20
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # 中心小点
        p.setBrush(QColor(255, 50, 50))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - 3, cy - 3, 6, 6)

        # 坐标标注（显示物理像素坐标）
        p.setPen(QColor(255, 50, 50))
        font = p.font()
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        p.drawText(cx + 25, cy - 8, f"({self._phys_cx}, {self._phys_cy})")
        p.end()


# ==========================================
# 光标设置页面
# ==========================================

class CursorPage(ScrollArea):
    """光标设置页面"""

    def __init__(self, db: DBManager, triangle_cursor=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._triangle_cursor = triangle_cursor
        self._crosshair = None
        self._crosshair_visible = False
        self.setObjectName("cursorPage")
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

        # 实时光标坐标定时器
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._update_cursor_pos)
        self._cursor_timer.start(50)

    def _build(self):
        # 卡片1：实时光标监控
        c1 = FluentCard("实时光标监控", "显示当前鼠标光标的物理像素坐标 (50ms 刷新)。")
        coord_row = QHBoxLayout()
        coord_row.setSpacing(40)
        self._cursor_x_label = SubtitleLabel("X：—")
        self._cursor_x_label.setStyleSheet(
            "color: #005FB8; font-family: 'Cascadia Code', 'Consolas', monospace;")
        self._cursor_y_label = SubtitleLabel("Y：—")
        self._cursor_y_label.setStyleSheet(
            "color: #005FB8; font-family: 'Cascadia Code', 'Consolas', monospace;")
        coord_row.addWidget(self._cursor_x_label)
        coord_row.addWidget(self._cursor_y_label)
        coord_row.addStretch()
        c1.add_layout(coord_row)
        self.lay.addWidget(c1)

        # 卡片2：定点压力测试
        c2 = FluentCard("定点测试",
                         "输入 0–1000 归一化坐标，光标将飞向对应位置并停留 15 秒。\n"
                         "500,500 = 屏幕正中央")
        test_row = QHBoxLayout()
        test_row.setSpacing(12)
        self._test_x = LineEdit()
        self._test_x.setText("500")
        self._test_x.setPlaceholderText("X (0–1000)")
        self._test_x.setFixedWidth(130)
        self._test_x.setMinimumHeight(36)
        self._test_y = LineEdit()
        self._test_y.setText("500")
        self._test_y.setPlaceholderText("Y (0–1000)")
        self._test_y.setFixedWidth(130)
        self._test_y.setMinimumHeight(36)
        test_btn = PrimaryPushButton("即时移动")
        test_btn.setFixedWidth(120)
        test_btn.setMinimumHeight(36)
        test_btn.clicked.connect(self._test_move)
        test_row.addWidget(BodyLabel("X："))
        test_row.addWidget(self._test_x)
        test_row.addWidget(BodyLabel("Y："))
        test_row.addWidget(self._test_y)
        test_row.addWidget(test_btn)
        test_row.addStretch()
        c2.add_layout(test_row)
        c2.add_divider()

        # 屏幕中心准星切换按钮
        crosshair_row = QHBoxLayout()
        self._crosshair_btn = PushButton("🎯 显示屏幕中心")
        self._crosshair_btn.setMinimumHeight(36)
        self._crosshair_btn.setToolTip("在物理屏幕正中央显示/隐藏准星。")
        self._crosshair_btn.clicked.connect(self._toggle_crosshair)
        crosshair_row.addWidget(self._crosshair_btn)
        crosshair_row.addStretch()
        c2.add_layout(crosshair_row)
        self.lay.addWidget(c2)

        # 卡片3：全局偏移（实时预览）
        c3 = FluentCard("全局定位偏移量",
                         "在归一化坐标空间内叠加统一补偿，消除系统性定位偏差。\n"
                         "修改后立即生效（光标会飞向 500,500 + 偏移量 的位置）。")
        off_row = QHBoxLayout()
        off_row.setSpacing(12)
        self._offset_x = LineEdit()
        self._offset_x.setText(self.db.get("offset_x", "0"))
        self._offset_x.setPlaceholderText("0")
        self._offset_x.setFixedWidth(130)
        self._offset_x.setMinimumHeight(36)
        self._offset_y = LineEdit()
        self._offset_y.setText(self.db.get("offset_y", "0"))
        self._offset_y.setPlaceholderText("0")
        self._offset_y.setFixedWidth(130)
        self._offset_y.setMinimumHeight(36)

        # 实时偏移预览：输入变化时自动飞行
        self._offset_x.textChanged.connect(self._on_offset_changed)
        self._offset_y.textChanged.connect(self._on_offset_changed)

        off_row.addWidget(BodyLabel("偏移 X："))
        off_row.addWidget(self._offset_x)
        off_row.addWidget(BodyLabel("偏移 Y："))
        off_row.addWidget(self._offset_y)
        off_row.addStretch()
        c3.add_layout(off_row)

        hint = BodyLabel("正数向右/下偏移，负数向左/上偏移。参考实时坐标进行调校。")
        hint.setStyleSheet("color: #767676;")
        c3.add_widget(hint)
        self.lay.addWidget(c3)

        self.lay.addStretch()

    def _update_cursor_pos(self):
        """实时更新光标坐标（显示物理像素坐标）"""
        pos = QCursor.pos()
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
        # 逻辑坐标 × DPR = 物理像素
        phys_x = int(pos.x() * ratio)
        phys_y = int(pos.y() * ratio)
        self._cursor_x_label.setText(f"X：{phys_x}")
        self._cursor_y_label.setText(f"Y：{phys_y}")

    def _toggle_crosshair(self):
        """切换准星显示/隐藏"""
        if self._crosshair_visible:
            self._hide_crosshair()
            self._crosshair_btn.setText("🎯 显示屏幕中心")
        else:
            self._show_crosshair()
            self._crosshair_btn.setText("✖ 隐藏屏幕中心")

    def _show_crosshair(self):
        from screen import get_screen_size
        sw, sh = get_screen_size()
        cx, cy = sw // 2, sh // 2

        if self._crosshair is not None:
            self._crosshair.close()

        self._crosshair = CrosshairOverlay(cx, cy)
        self._crosshair.show()
        self._crosshair_visible = True
        logger.info("显示屏幕中心准星: (%d, %d)", cx, cy)

    def _hide_crosshair(self):
        if self._crosshair is not None:
            self._crosshair.close()
            self._crosshair = None
        self._crosshair_visible = False

    def _on_offset_changed(self):
        """偏移量输入变化时实时预览——飞向 500,500 + 偏移量"""
        if not self._triangle_cursor:
            return
        try:
            ox = int(self._offset_x.text().strip() or "0")
            oy = int(self._offset_y.text().strip() or "0")
        except ValueError:
            return
        from screen import get_screen_size
        sw, sh = get_screen_size()
        # 500,500 是屏幕中心归一化坐标，叠加偏移后换算为物理像素
        px = int(((500 + ox) / 1000) * sw)
        py = int(((500 + oy) / 1000) * sh)
        self._triangle_cursor.test_move_to(px, py, duration_sec=8)

    def _test_move(self):
        if not self._triangle_cursor:
            return
        try:
            nx = int(self._test_x.text().strip())
            ny = int(self._test_y.text().strip())
        except ValueError:
            return
        try:
            ox = int(self._offset_x.text().strip() or "0")
            oy = int(self._offset_y.text().strip() or "0")
        except ValueError:
            ox, oy = 0, 0
        final_nx = nx + ox
        final_ny = ny + oy
        from screen import get_screen_size
        sw, sh = get_screen_size()
        px = int((final_nx / 1000) * sw)
        py = int((final_ny / 1000) * sh)
        logger.info("定点测试: 归一化(%d,%d) + 偏移(%d,%d) → 物理像素(%d,%d)",
                    nx, ny, ox, oy, px, py)
        self._triangle_cursor.test_move_to(px, py, duration_sec=15)
