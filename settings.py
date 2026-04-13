# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
settings.py - MoCli 设置窗口
====================================================
使用 PyQt6-Fluent-Widgets (MSFluentWindow) 构建 Windows 11 原生流畅设计风格。
Qt 高 DPI 缩放已全局启用（main.py），此处无需手动缩放。
"""

import os
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QApplication, QTextBrowser, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QFont, QIcon, QCursor, QPainter, QColor, QPen

from qfluentwidgets import (
    MSFluentWindow, FluentIcon, SubtitleLabel, BodyLabel,
    LineEdit, PrimaryPushButton, PushButton,
    SwitchButton, Slider, TextEdit,
    ScrollArea, InfoBar, InfoBarPosition,
    NavigationItemPosition, setFont
)

from db import DBManager
from utils import static

logger = logging.getLogger(__name__)


# ==========================================
# 设置卡片组件
# ==========================================

class FluentCard(QFrame):
    """Win11 风格设置卡片：白底圆角容器"""
    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        self.setObjectName("fluentCard")
        self.setStyleSheet("""
            QFrame#fluentCard {
                background-color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(6)

        if title:
            t = SubtitleLabel(title)
            setFont(t, 18, QFont.Weight.DemiBold)
            lay.addWidget(t)
        if description:
            d = BodyLabel(description)
            d.setWordWrap(True)
            d.setStyleSheet("color: #767676;")
            lay.addWidget(d)
        if title or description:
            lay.addSpacing(12)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(12)
        lay.addLayout(self.content_layout)

    def add_widget(self, w: QWidget):
        self.content_layout.addWidget(w)

    def add_layout(self, l):
        self.content_layout.addLayout(l)

    def add_divider(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background: #EEEEEE; max-height: 1px;")
        self.content_layout.addWidget(f)

    def add_row(self, label_text: str, widget: QWidget) -> QWidget:
        """添加 标题+控件 的行"""
        lbl = BodyLabel(label_text)
        lbl.setStyleSheet("color: #4A4A4A; font-weight: 500;")
        self.content_layout.addWidget(lbl)
        widget.setMinimumHeight(36)
        self.content_layout.addWidget(widget)
        return widget


# ==========================================
# 页面：大模型引擎
# ==========================================

class LLMPage(ScrollArea):
    """大模型引擎配置页面"""

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("llmPage")
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
        # 卡片1：API 连接配置
        c1 = FluentCard("API 连接配置", "配置与大语言模型 (VLM) 服务的通信参数。")
        self.url_input = LineEdit()
        self.url_input.setText(self.db.get("base_url"))
        self.url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        c1.add_row("Base URL（端点地址）", self.url_input)
        c1.add_divider()

        self.model_input = LineEdit()
        self.model_input.setText(self.db.get("model"))
        self.model_input.setPlaceholderText("例如：qwen-vl-max  /  gpt-4o")
        c1.add_row("模型标识码 (Model ID)", self.model_input)
        c1.add_divider()

        self.api_key_input = LineEdit()
        self.api_key_input.setText(self.db.get("api_key"))
        self.api_key_input.setEchoMode(LineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        c1.add_row("API 密钥 (API Key)", self.api_key_input)
        self.lay.addWidget(c1)

        # 卡片2：对话记忆
        c2 = FluentCard("对话记忆", "设定 AI 可以回忆的最近历史对话轮数。数值越大，消耗 Token 越多。")
        mem_val = self.db.get_int("memory_size")
        self._mem_label = BodyLabel(f"当前容量：{mem_val} 条历史对话")
        c2.add_widget(self._mem_label)

        self.memory_slider = Slider(Qt.Orientation.Horizontal)
        self.memory_slider.setRange(2, 50)
        self.memory_slider.setValue(mem_val)
        self.memory_slider.setMinimumHeight(32)
        self.memory_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.memory_slider.installEventFilter(self)
        self.memory_slider.valueChanged.connect(
            lambda v: self._mem_label.setText(f"当前容量：{v} 条历史对话")
        )
        c2.add_widget(self.memory_slider)

        hint = BodyLabel("推荐值：6–16 条。设置过高可能导致响应速度变慢。")
        hint.setStyleSheet("color: #767676;")
        c2.add_widget(hint)
        self.lay.addWidget(c2)

        # 卡片3：系统提示词
        c3 = FluentCard("系统提示词 (System Prompt)",
                         "定义 AI 的个性与行为准则。可直接编辑内置默认提示词或替换为自定义内容。")
        self.prompt_edit = TextEdit()
        # 加载已保存的自定义提示词，如果没有则显示内置默认提示词
        saved_prompt = self.db.get("custom_system_prompt", "").strip()
        if saved_prompt:
            self.prompt_edit.setPlainText(saved_prompt)
        else:
            from llm import LLMEngine
            self.prompt_edit.setPlainText(LLMEngine.DEFAULT_SYSTEM_PROMPT)
        self.prompt_edit.setMinimumHeight(250)
        c3.add_widget(self.prompt_edit)

        btn_row = QHBoxLayout()
        reset_btn = PushButton("恢复内置默认")
        reset_btn.setMinimumHeight(36)
        reset_btn.clicked.connect(self._reset_prompt)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        c3.add_layout(btn_row)
        self.lay.addWidget(c3)

        self.lay.addStretch()

    def _reset_prompt(self):
        """恢复内置默认提示词"""
        from llm import LLMEngine
        self.prompt_edit.setPlainText(LLMEngine.DEFAULT_SYSTEM_PROMPT)

    def eventFilter(self, obj, event):
        """拦截滑块的滚轮事件，防止滚动页面时误触"""
        if hasattr(self, 'memory_slider') and obj is self.memory_slider and event.type() == QEvent.Type.Wheel:
            return True  # 吐掉滚轮事件
        return super().eventFilter(obj, event)


# ==========================================
# 页面：语音交互
# ==========================================

class VoicePage(ScrollArea):
    """语音交互配置页面"""

    def __init__(self, db: DBManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("voicePage")
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
        # 卡片1：语音唤醒
        c1 = FluentCard("语音唤醒 (KWS)", "说出唤醒词自动激活麦克风，也可按 F10 直接唤醒。")
        row_wake = QHBoxLayout()
        row_wake.addWidget(BodyLabel("启用语音唤醒"))
        row_wake.addStretch()
        self.wakeup_switch = SwitchButton()
        self.wakeup_switch.setChecked(self.db.get_bool("wakeup_enabled"))
        row_wake.addWidget(self.wakeup_switch)
        c1.add_layout(row_wake)
        c1.add_divider()

        self.keyword_input = LineEdit()
        self.keyword_input.setText(self.db.get("wakeup_keyword"))
        self.keyword_input.setPlaceholderText("贾维斯")
        c1.add_row("唤醒词（纯中文）", self.keyword_input)

        self._kw_preview = BodyLabel("拼音预览：（输入唤醒词后自动生成）")
        self._kw_preview.setWordWrap(True)
        self._kw_preview.setStyleSheet("color: #767676;")
        c1.add_widget(self._kw_preview)

        preview_btn = PushButton("预览拼音")
        preview_btn.setMinimumHeight(36)
        preview_btn.clicked.connect(self._preview_keyword)
        c1.add_widget(preview_btn)

        # 初始化预览
        saved_lines = self.db.get("keyword_lines", "")
        if saved_lines:
            self._kw_preview.setText("已保存的拼音：" + saved_lines)
        self.keyword_input.textChanged.connect(self._preview_keyword)
        self.lay.addWidget(c1)

        # 卡片2：语音合成
        c2 = FluentCard("语音合成 (TTS)", "AI 回复将通过 TTS 服务自动朗读。")
        row_tts = QHBoxLayout()
        row_tts.addWidget(BodyLabel("启用 AI 语音回复"))
        row_tts.addStretch()
        self.tts_switch = SwitchButton()
        self.tts_switch.setChecked(self.db.get_bool("tts_enabled"))
        row_tts.addWidget(self.tts_switch)
        c2.add_layout(row_tts)
        c2.add_divider()

        self.tts_url_input = LineEdit()
        self.tts_url_input.setText(self.db.get("tts_url"))
        self.tts_url_input.setPlaceholderText("http://localhost:8100/v1/audio/speech")
        c2.add_row("TTS 服务地址", self.tts_url_input)
        c2.add_divider()

        self.tts_model_input = LineEdit()
        self.tts_model_input.setText(self.db.get("tts_model"))
        self.tts_model_input.setPlaceholderText("model-base")
        c2.add_row("TTS 语音模型标识", self.tts_model_input)
        self.lay.addWidget(c2)

        self.lay.addStretch()

    def _preview_keyword(self):
        from wakeup import WakeupEngine
        text = self.keyword_input.text().strip()
        if not text:
            self._kw_preview.setText("拼音预览：（请输入中文唤醒词）")
            return
        lines = WakeupEngine.chinese_to_keyword_lines(text)
        if lines:
            self._kw_preview.setText("拼音预览：\n" + "\n".join(lines))
        else:
            self._kw_preview.setText("⚠️ pypinyin 未安装，无法生成拼音")


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
# 页面：光标设置
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


# ==========================================
# 页面：关于
# ==========================================

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
        lay = QVBoxLayout(content)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(20)
        self.setWidget(content)

        # 无标题卡片，直接放置 QTextBrowser 占满全部空间
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

        # 加载并渲染免责声明
        md_path = static("免责声明.md")
        if os.path.isfile(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            html = self._render_markdown(md_text)
            self._browser.setHtml(html)
        else:
            self._browser.setPlainText("未找到免责声明文件。")

        lay.addWidget(self._browser)

    @staticmethod
    def _render_markdown(md_text: str) -> str:
        """使用 markdown 库渲染 Markdown → HTML（带内联样式）"""
        import markdown as md_lib
        body = md_lib.markdown(md_text, extensions=["extra"])
        # 注入 CSS 样式让 QTextBrowser 显示更美观
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


# ==========================================
# SettingsWindow — PyQt6-Fluent-Widgets
# ==========================================

class SettingsWindow(MSFluentWindow):
    """MoCli 设置窗口 — Windows 11 原生 Fluent Design 风格"""

    def __init__(self, triangle_cursor=None, parent=None):
        super().__init__(parent)
        self.db = DBManager()
        self._triangle_cursor = triangle_cursor

        # 创建子页面
        self.llm_page = LLMPage(self.db, self)
        self.voice_page = VoicePage(self.db, self)
        self.cursor_page = CursorPage(self.db, triangle_cursor, self)
        self.about_page = AboutPage(self)

        self._init_navigation()
        self._init_window()

    def _init_navigation(self):
        """配置侧边栏导航项"""
        self.addSubInterface(self.llm_page, FluentIcon.IOT, "大模型引擎")
        self.addSubInterface(self.voice_page, FluentIcon.MICROPHONE, "语音交互")
        self.addSubInterface(self.cursor_page, FluentIcon.MOVE, "光标设置")
        self.addSubInterface(self.about_page, FluentIcon.INFO, "关于")

        # 底部：保存按钮
        self.navigationInterface.addItem(
            routeKey='save_action',
            icon=FluentIcon.SAVE,
            text='保存设置',
            onClick=self._save_and_notify,
            position=NavigationItemPosition.BOTTOM
        )

    def _init_window(self):
        """配置窗口属性"""
        self.resize(960, 700)
        self.setMinimumSize(700, 500)
        self.setWindowTitle("MoCli 设置中心")

        # 设置窗口图标
        ico_path = static("mocli-logo.ico")
        png_path = static("mocli-logo-512x512.png")
        if os.path.isfile(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        elif os.path.isfile(png_path):
            self.setWindowIcon(QIcon(png_path))

        # 居中显示
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    def _save_and_notify(self):
        """保存并显示成功提示"""
        self._save()
        InfoBar.success(
            title='已保存',
            content='所有设置已成功保存到数据库',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def closeEvent(self, event):
        """关闭窗口时检查是否有未保存的更改"""
        if hasattr(self.cursor_page, '_cursor_timer'):
            self.cursor_page._cursor_timer.stop()
        self.cursor_page._hide_crosshair()

        # 检查是否有未保存的修改
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "您有未保存的设置更改，是否在关闭前保存？",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
                return
        else:
            event.accept()

        super().closeEvent(event)

    def _has_unsaved_changes(self) -> bool:
        """检查当前 UI 值是否与数据库中已保存的值不同"""
        db = self.db
        checks = [
            db.get("base_url") != self.llm_page.url_input.text().strip(),
            db.get("model") != self.llm_page.model_input.text().strip(),
            db.get("api_key") != self.llm_page.api_key_input.text().strip(),
            db.get_int("memory_size") != self.llm_page.memory_slider.value(),
            db.get("custom_system_prompt", "").strip() != self.llm_page.prompt_edit.toPlainText().strip(),
            db.get("wakeup_keyword") != self.voice_page.keyword_input.text().strip(),
            db.get_bool("wakeup_enabled") != self.voice_page.wakeup_switch.isChecked(),
            db.get_bool("tts_enabled") != self.voice_page.tts_switch.isChecked(),
            db.get("tts_url") != self.voice_page.tts_url_input.text().strip(),
            db.get("tts_model") != self.voice_page.tts_model_input.text().strip(),
        ]
        return any(checks)

    def _save(self):
        """保存所有配置到数据库"""
        # 大模型设置
        self.db.set("base_url", self.llm_page.url_input.text().strip())
        self.db.set("model", self.llm_page.model_input.text().strip())
        self.db.set("api_key", self.llm_page.api_key_input.text().strip())
        self.db.set("memory_size", str(self.llm_page.memory_slider.value()))
        custom_prompt = self.llm_page.prompt_edit.toPlainText().strip()
        self.db.set("custom_system_prompt", custom_prompt)

        # 唤醒词设置
        self.db.set("wakeup_enabled", str(self.voice_page.wakeup_switch.isChecked()).lower())
        keyword = self.voice_page.keyword_input.text().strip()
        self.db.set("wakeup_keyword", keyword)
        if keyword:
            from wakeup import WakeupEngine
            lines = WakeupEngine.chinese_to_keyword_lines(keyword)
            if lines:
                self.db.set("keyword_lines", "\n".join(lines))

        # TTS 设置
        self.db.set("tts_enabled", str(self.voice_page.tts_switch.isChecked()).lower())
        self.db.set("tts_url", self.voice_page.tts_url_input.text().strip())
        self.db.set("tts_model", self.voice_page.tts_model_input.text().strip())

        # 偏移量
        try:
            self.db.set("offset_x", str(int(self.cursor_page._offset_x.text().strip() or "0")))
            self.db.set("offset_y", str(int(self.cursor_page._offset_y.text().strip() or "0")))
        except ValueError:
            pass

        logger.info("所有设置已保存")
