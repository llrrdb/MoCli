# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
llm_page.py - 大模型引擎配置页面
===================================
管理 VLM 连接参数（Base URL、Model ID、API Key）、对话记忆和系统提示词。
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
    LineEdit, PrimaryPushButton, PushButton,
    Slider, TextEdit,
    ScrollArea, InfoBar, InfoBarPosition,
)

from db import DBManager
from settings.cards import FluentCard

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

        # 连接跨线程回调信号
        self._test_signal.connect(self._on_test_done)

        self._build()

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

        # 卡片1：API 连接配置
        c1 = FluentCard("API 连接配置", "配置与大语言模型 (VLM) 服务的通信参数。选择预设平台体验自动回填。")

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
            QComboBox::drop-down {
                border: none;
            }
        """)
        for k in self.preset_providers.keys():
            self.provider_combo.addItem(k)

        # 尝试通过当前的 base_url 倒推匹配当前的 provider 下拉列表位置
        current_url = self.db.get("base_url", "")
        matched_idx = list(self.preset_providers.keys()).index("【自定义 / 第三方兼容】")
        for i, (k, v) in enumerate(self.preset_providers.items()):
            if v["url"] and current_url == v["url"]:
                matched_idx = i
                break
        self.provider_combo.setCurrentIndex(matched_idx)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        c1.add_row("平台预设 (Provider)", self.provider_combo)
        c1.add_divider()

        self.url_input = LineEdit()
        self.url_input.setText(self.db.get("base_url"))
        self.url_input.setPlaceholderText("https://api.example.com/v1")
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
        c1.add_divider()

        self.test_btn = PrimaryPushButton("测试连接验证")
        self.test_btn.clicked.connect(self._test_connection)

        btn_ly = QHBoxLayout()
        btn_ly.addStretch()
        btn_ly.addWidget(self.test_btn)
        c1.add_layout(btn_ly)

        self.lay.addWidget(c1)

        # 构建剩余卡片（对话记忆 + 系统提示词）
        self._build_card2_and_card3()

    def _on_provider_changed(self, idx):
        provider_name = self.provider_combo.currentText()
        preset = self.preset_providers.get(provider_name)
        if preset and provider_name != "【自定义 / 第三方兼容】":
            if preset["url"]:
                self.url_input.setText(preset["url"])
            else:
                self.url_input.clear()

            # 使用原生自带 URL 时清空占位
            if not preset["url"]:
                self.url_input.setPlaceholderText("该平台由客户端原生支持，通常无需填写 Base URL")
            else:
                self.url_input.setPlaceholderText("https://api.example.com/v1")

            if preset["model"]:
                self.model_input.setText(preset["model"])

        elif provider_name == "【自定义 / 第三方兼容】":
            self.url_input.setPlaceholderText("请输入第三方接口基地址 (应当包含 /v1)")

    def _test_connection(self):
        """发起对该设定的临时握手网络测速连接"""
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试通讯中...")
        InfoBar.info(
            title="请求已发出",
            content="LiteLLM 正在向选定的大模型下发握手握手，请耐心等待...",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window()
        )

        test_url = self.url_input.text().strip()
        test_key = self.api_key_input.text().strip()
        test_model = self.model_input.text().strip()

        # 剥离主线程开子线程做 HTTP 连接，不阻塞 UI 动效滚动
        def worker():
            import litellm
            from litellm import completion
            try:
                # 路由逻辑与 llm.py 保持一致
                model_route = test_model or "undefined"
                if test_url:
                    # 有 base_url 时: 走 openai 兼容通道，剥离非标前缀
                    if "/" in model_route:
                        model_route = model_route.split("/", 1)[1]
                    model_route = f"openai/{model_route}"

                kwargs = {
                    "model": model_route,
                    "messages": [{"role": "user", "content": "你好，这是一条连接测试消息，请你仅回复「连接成功」这四个字，不需要其他废话。"}],
                    "temperature": 0.1,
                    "max_tokens": 15
                }

                # 兼容虚假凭据（像 Ollama 这种没密码的）
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

    def _build_card2_and_card3(self):
        """构建对话记忆和系统提示词卡片（由 _build 调用）"""
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
