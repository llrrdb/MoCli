# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
llm_page.py - 大模型引擎配置页面
===================================
管理 VLM 连接参数、对话记忆和系统提示词。
使用 SettingCardGroup + SettingCard/PrimaryPushSettingCard，Fluent Design 风格。
"""

import logging
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QFont

from qfluentwidgets import (
    BodyLabel,
    LineEdit, PrimaryPushSettingCard, PushButton,
    SettingCard, SettingCardGroup,
    Slider, TextEdit,
    FluentIcon,
    ScrollArea, InfoBar, InfoBarPosition,
)

from db import DBManager

logger = logging.getLogger(__name__)


class LLMPage(ScrollArea):
    """大模型引擎配置页面"""
    # 跨线程安全信号：用于子线程将测试结果回传到 UI 主线程
    _test_signal = pyqtSignal(bool, str)

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

        self._test_signal.connect(self._on_test_done)
        self._build()
        self.lay.addStretch()

    def _build(self):
        # 预设集合
        self.preset_providers = {
            "Google (Gemini)": {"url": "", "model": "gemini/gemini-2.0-flash"},
            "阿里云百炼 (Qwen)": {"url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-max"},
            "OpenAI (ChatGPT)": {"url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
            "Anthropic (Claude)": {"url": "", "model": "anthropic/claude-3-7-sonnet-20250219"},
            "智谱 AI (GLM)": {"url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4v"},
            "本地或跨平台代理 (LM Studio/Ollama)": {"url": "http://127.0.0.1:1234/v1", "model": "local-model"},
            "【自定义 / 第三方兼容】": {"url": "", "model": ""}
        }

        # ==========================================
        # 卡片组1：API 连接配置
        # ==========================================
        api_group = SettingCardGroup("API 连接配置", self)

        # 1a. 平台预设
        provider_card = SettingCard(
            FluentIcon.GLOBE,
            "平台预设 (Provider)",
            "选择预设模型平台，自动回填地址与模型标识",
            self
        )
        self.provider_combo = QComboBox()
        self.provider_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid rgba(0, 0, 0, 0.073);
                border-radius: 5px;
                padding: 6px 12px;
                background-color: rgba(255, 255, 255, 0.7);
                font-family: "Microsoft YaHei", sans-serif;
                font-size: 14px;
                min-height: 24px;
            }
            QComboBox::drop-down { border: none; }
        """)
        for k in self.preset_providers.keys():
            self.provider_combo.addItem(k)

        current_url = self.db.get("base_url", "")
        matched_idx = list(self.preset_providers.keys()).index("【自定义 / 第三方兼容】")
        for i, (k, v) in enumerate(self.preset_providers.items()):
            if v["url"] and current_url == v["url"]:
                matched_idx = i
                break
        self.provider_combo.setCurrentIndex(matched_idx)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.provider_combo.setMinimumWidth(250)

        provider_card.hBoxLayout.addWidget(self.provider_combo, 0, Qt.AlignmentFlag.AlignRight)
        provider_card.hBoxLayout.addSpacing(16)
        api_group.addSettingCard(provider_card)

        # 1b. Base URL
        url_card = SettingCard(
            FluentIcon.GLOBE,
            "Base URL（端点地址）",
            "API 服务端点，兼容 OpenAI 接口格式",
            self
        )
        self.url_input = LineEdit()
        self.url_input.setText(self.db.get("base_url"))
        self.url_input.setPlaceholderText("https://api.example.com/v1")
        self.url_input.setMinimumWidth(280)
        url_card.hBoxLayout.addWidget(self.url_input, 0, Qt.AlignmentFlag.AlignRight)
        url_card.hBoxLayout.addSpacing(16)
        api_group.addSettingCard(url_card)

        # 1c. 模型标识
        model_card = SettingCard(
            FluentIcon.CODE,
            "模型标识码 (Model ID)",
            "例如：qwen-vl-max / gpt-4o",
            self
        )
        self.model_input = LineEdit()
        self.model_input.setText(self.db.get("model"))
        self.model_input.setPlaceholderText("qwen-vl-max / gpt-4o")
        self.model_input.setMinimumWidth(200)
        model_card.hBoxLayout.addWidget(self.model_input, 0, Qt.AlignmentFlag.AlignRight)
        model_card.hBoxLayout.addSpacing(16)
        api_group.addSettingCard(model_card)

        # 1d. API Key
        key_card = SettingCard(
            FluentIcon.GLOBE,
            "API 密钥 (API Key)",
            "输入您的 API 认证密钥",
            self
        )
        self.api_key_input = LineEdit()
        self.api_key_input.setText(self.db.get("api_key"))
        self.api_key_input.setEchoMode(LineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        self.api_key_input.setMinimumWidth(200)
        key_card.hBoxLayout.addWidget(self.api_key_input, 0, Qt.AlignmentFlag.AlignRight)
        key_card.hBoxLayout.addSpacing(16)
        api_group.addSettingCard(key_card)

        # 1e. 测试连接
        self._test_card = PrimaryPushSettingCard(
            "测试连接验证",
            FluentIcon.SEND,
            "连接测试",
            "发起一次 API 握手请求，验证配置是否正确",
            parent=self
        )
        self._test_card.clicked.connect(self._test_connection)
        api_group.addSettingCard(self._test_card)

        self.lay.addWidget(api_group)

        # ==========================================
        # 卡片组2：对话配置
        # ==========================================
        mem_group = SettingCardGroup("对话配置", self)

        # 2a. 对话记忆
        mem_card = SettingCard(
            FluentIcon.HISTORY,
            "对话记忆",
            "设定 AI 可回忆的最近历史对话轮数。数值越大，消耗 Token 越多",
            self
        )
        mem_val = self.db.get_int("memory_size")
        self._mem_label = BodyLabel(f"{mem_val} 条")
        self._mem_label.setStyleSheet("color: #005FB8; font-weight: 600; min-width: 40px;")

        self.memory_slider = Slider(Qt.Orientation.Horizontal)
        self.memory_slider.setRange(2, 50)
        self.memory_slider.setValue(mem_val)
        self.memory_slider.setMinimumWidth(160)
        self.memory_slider.setMinimumHeight(32)
        self.memory_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.memory_slider.installEventFilter(self)
        self.memory_slider.valueChanged.connect(
            lambda v: self._mem_label.setText(f"{v} 条")
        )

        slider_widget = QWidget()
        slider_row = QHBoxLayout(slider_widget)
        slider_row.setSpacing(8)
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.addWidget(self.memory_slider)
        slider_row.addWidget(self._mem_label)

        mem_card.hBoxLayout.addWidget(slider_widget, 0, Qt.AlignmentFlag.AlignRight)
        mem_card.hBoxLayout.addSpacing(16)
        mem_group.addSettingCard(mem_card)

        # 2b. 系统提示词
        prompt_card = SettingCard(
            FluentIcon.DOCUMENT,
            "系统提示词 (System Prompt)",
            "定义 AI 的个性与行为准则，可直接编辑或恢复默认",
            self
        )
        mem_group.addSettingCard(prompt_card)

        self.lay.addWidget(mem_group)

        # 系统提示词编辑区（放在组外的独立区域）
        self.prompt_edit = TextEdit()
        saved_prompt = self.db.get("custom_system_prompt", "").strip()
        if saved_prompt:
            self.prompt_edit.setPlainText(saved_prompt)
        else:
            from llm import LLMEngine
            self.prompt_edit.setPlainText(LLMEngine.DEFAULT_SYSTEM_PROMPT)
        self.prompt_edit.setMinimumHeight(250)
        self.prompt_edit.setStyleSheet("""
            TextEdit {
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.7);
                padding: 12px;
            }
        """)
        self.lay.addWidget(self.prompt_edit)

        # 恢复默认按钮
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = PushButton("恢复内置默认")
        reset_btn.setMinimumHeight(36)
        reset_btn.clicked.connect(self._reset_prompt)
        reset_row.addWidget(reset_btn)
        self.lay.addLayout(reset_row)

    # ==========================================
    # 属性别名 — 保持内部兼容
    # ==========================================

    @property
    def test_btn(self):
        """向后兼容：返回测试卡片的内部按钮"""
        return self._test_card.button

    # ==========================================
    # Provider 预设切换
    # ==========================================

    def _on_provider_changed(self, idx):
        provider_name = self.provider_combo.currentText()
        preset = self.preset_providers.get(provider_name)
        if preset and provider_name != "【自定义 / 第三方兼容】":
            if preset["url"]:
                self.url_input.setText(preset["url"])
            else:
                self.url_input.clear()
            if not preset["url"]:
                self.url_input.setPlaceholderText("该平台由客户端原生支持，通常无需填写 Base URL")
            else:
                self.url_input.setPlaceholderText("https://api.example.com/v1")
            if preset["model"]:
                self.model_input.setText(preset["model"])
        elif provider_name == "【自定义 / 第三方兼容】":
            self.url_input.setPlaceholderText("请输入第三方接口基地址 (应当包含 /v1)")

    # ==========================================
    # 连接测试
    # ==========================================

    def _test_connection(self):
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试通讯中...")
        InfoBar.info(
            title="请求已发出",
            content="LiteLLM 正在向选定的大模型下发握手请求，请耐心等待...",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window()
        )

        test_url = self.url_input.text().strip()
        test_key = self.api_key_input.text().strip()
        test_model = self.model_input.text().strip()

        def worker():
            from litellm import completion
            try:
                model_route = test_model or "undefined"
                if test_url:
                    if "/" in model_route:
                        model_route = model_route.split("/", 1)[1]
                    model_route = f"openai/{model_route}"

                kwargs = {
                    "model": model_route,
                    "messages": [{"role": "user", "content": "你好，这是一条连接测试消息，请你仅回复「连接成功」这四个字，不需要其他废话。"}],
                    "temperature": 0.1,
                    "max_tokens": 15
                }
                if test_key:
                    kwargs["api_key"] = test_key
                else:
                    kwargs["api_key"] = "dummy"
                if test_url:
                    kwargs["api_base"] = test_url

                response = completion(**kwargs)
                res_text = response.choices[0].message.content
                self._test_signal.emit(True, res_text)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._test_signal.emit(False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, success, msg):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("测试连接验证")
        if success:
            InfoBar.success(
                title="接口测试完美通过！",
                content=f"AI 服务端已正确握手返回：{msg}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self.window()
            )
        else:
            InfoBar.error(
                title="抱歉，通道连接异常中断",
                content=f"错误反馈栈：{msg}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=0,
                parent=self.window()
            )

    # ==========================================
    # 系统提示词
    # ==========================================

    def _reset_prompt(self):
        from llm import LLMEngine
        self.prompt_edit.setPlainText(LLMEngine.DEFAULT_SYSTEM_PROMPT)

    # ==========================================
    # 滑块滚轮拦截
    # ==========================================

    def eventFilter(self, obj, event):
        if hasattr(self, 'memory_slider') and obj is self.memory_slider and event.type() == QEvent.Type.Wheel:
            return True
        return super().eventFilter(obj, event)
