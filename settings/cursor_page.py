# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
cursor_page.py - 光标设置页面
================================
包含实时光标坐标监控、定点飞行测试、全局偏移量校准和屏幕中心准星。
使用 SettingCardGroup + SettingCard/PushSettingCard，Fluent Design 风格。
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
    SettingCard, PushSettingCard,
    SettingCardGroup, FluentIcon,
    ScrollArea,
)

from db import DBManager

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

        size = 200
        self.resize(size, size)

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

        gap, arm = 8, 50
        p.drawLine(cx - arm, cy, cx - gap, cy)
        p.drawLine(cx + gap, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy - gap)
        p.drawLine(cx, cy + gap, cx, cy + arm)

        r = 20
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.setBrush(QColor(255, 50, 50))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - 3, cy - 3, 6, 6)

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
        self.lay.addStretch()

        # 实时光标坐标定时器
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._update_cursor_pos)
        self._cursor_timer.start(50)

    def _build(self):
        # ==========================================
        # 卡片组1：实时光标监控
        # ==========================================
        monitor_group = SettingCardGroup("实时光标监控", self)

        cursor_card = SettingCard(
            FluentIcon.MOVE,
            "当前光标坐标",
            "50ms 实时刷新 — 物理像素坐标",
            self
        )
        # 将 X/Y 标签放入右侧
        coord_widget = QWidget()
        coord_row = QHBoxLayout(coord_widget)
        coord_row.setSpacing(24)
        coord_row.setContentsMargins(0, 0, 0, 0)
        self._cursor_x_label = SubtitleLabel("X：—")
        self._cursor_x_label.setStyleSheet(
            "color: #005FB8; font-family: 'Cascadia Code', 'Consolas', monospace;")
        self._cursor_y_label = SubtitleLabel("Y：—")
        self._cursor_y_label.setStyleSheet(
            "color: #005FB8; font-family: 'Cascadia Code', 'Consolas', monospace;")
        coord_row.addWidget(self._cursor_x_label)
        coord_row.addWidget(self._cursor_y_label)
        cursor_card.hBoxLayout.addWidget(coord_widget, 0, Qt.AlignmentFlag.AlignRight)
        cursor_card.hBoxLayout.addSpacing(16)
        monitor_group.addSettingCard(cursor_card)

        self.lay.addWidget(monitor_group)

        # ==========================================
        # 卡片组2：定点测试
        # ==========================================
        fly_group = SettingCardGroup("定点测试", self)

        fly_card = SettingCard(
            FluentIcon.SEND,
            "移动到指定坐标",
            "0–1000 归一化坐标，500,500 = 屏幕正中央，停留 15 秒",
            self
        )
        # 右侧：X/Y 输入 + 按钮
        fly_widget = QWidget()
        fly_row = QHBoxLayout(fly_widget)
        fly_row.setSpacing(8)
        fly_row.setContentsMargins(0, 0, 0, 0)

        fly_row.addWidget(BodyLabel("X："))
        self._test_x = LineEdit()
        self._test_x.setText("500")
        self._test_x.setPlaceholderText("0–1000")
        self._test_x.setFixedWidth(90)
        self._test_x.setMinimumHeight(36)
        fly_row.addWidget(self._test_x)

        fly_row.addWidget(BodyLabel("Y："))
        self._test_y = LineEdit()
        self._test_y.setText("500")
        self._test_y.setPlaceholderText("0–1000")
        self._test_y.setFixedWidth(90)
        self._test_y.setMinimumHeight(36)
        fly_row.addWidget(self._test_y)

        test_btn = PrimaryPushButton("移动")
        test_btn.setFixedWidth(72)
        test_btn.setMinimumHeight(36)
        test_btn.clicked.connect(self._test_move)
        fly_row.addWidget(test_btn)

        fly_card.hBoxLayout.addWidget(fly_widget, 0, Qt.AlignmentFlag.AlignRight)
        fly_card.hBoxLayout.addSpacing(16)
        fly_group.addSettingCard(fly_card)

        # 准星切换
        crosshair_card = PushSettingCard(
            "显示屏幕中心",
            FluentIcon.MOVE,
            "屏幕中心准星",
            "在物理屏幕正中央显示/隐藏校准准星",
            parent=self
        )
        self._crosshair_btn = crosshair_card  # 保留属性名兼容
        crosshair_card.clicked.connect(self._toggle_crosshair)
        fly_group.addSettingCard(crosshair_card)

        self.lay.addWidget(fly_group)

        # ==========================================
        # 卡片组3：全局偏移
        # ==========================================
        offset_group = SettingCardGroup("全局定位偏移量", self)

        offset_card = SettingCard(
            FluentIcon.ALIGNMENT,
            "偏移量校准",
            "正数向右/下偏移，负数向左/上偏移；修改后光标自动飞向预览位置",
            self
        )
        offset_widget = QWidget()
        offset_row = QHBoxLayout(offset_widget)
        offset_row.setSpacing(8)
        offset_row.setContentsMargins(0, 0, 0, 0)

        offset_row.addWidget(BodyLabel("X："))
        self._offset_x = LineEdit()
        self._offset_x.setText(self.db.get("offset_x", "0"))
        self._offset_x.setPlaceholderText("0")
        self._offset_x.setFixedWidth(80)
        self._offset_x.setMinimumHeight(36)
        offset_row.addWidget(self._offset_x)

        offset_row.addWidget(BodyLabel("Y："))
        self._offset_y = LineEdit()
        self._offset_y.setText(self.db.get("offset_y", "0"))
        self._offset_y.setPlaceholderText("0")
        self._offset_y.setFixedWidth(80)
        self._offset_y.setMinimumHeight(36)
        offset_row.addWidget(self._offset_y)

        offset_card.hBoxLayout.addWidget(offset_widget, 0, Qt.AlignmentFlag.AlignRight)
        offset_card.hBoxLayout.addSpacing(16)
        offset_group.addSettingCard(offset_card)

        # 实时偏移预览
        self._offset_x.textChanged.connect(self._on_offset_changed)
        self._offset_y.textChanged.connect(self._on_offset_changed)

        self.lay.addWidget(offset_group)

    # ==========================================
    # 实时坐标
    # ==========================================

    def _update_cursor_pos(self):
        pos = QCursor.pos()
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
        phys_x = int(pos.x() * ratio)
        phys_y = int(pos.y() * ratio)
        self._cursor_x_label.setText(f"X：{phys_x}")
        self._cursor_y_label.setText(f"Y：{phys_y}")

    # ==========================================
    # 准星
    # ==========================================

    def _toggle_crosshair(self):
        if self._crosshair_visible:
            self._hide_crosshair()
            self._crosshair_btn.button.setText("显示屏幕中心")
        else:
            self._show_crosshair()
            self._crosshair_btn.button.setText("隐藏屏幕中心")

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

    # ==========================================
    # 偏移量 & 测试飞行
    # ==========================================

    def _on_offset_changed(self):
        if not self._triangle_cursor:
            return
        try:
            ox = int(self._offset_x.text().strip() or "0")
            oy = int(self._offset_y.text().strip() or "0")
        except ValueError:
            return
        from screen import get_screen_size
        sw, sh = get_screen_size()
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
