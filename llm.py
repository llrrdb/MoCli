# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
llm.py - MoCli 大模型对话引擎
================================
负责：
  - 系统提示词构建
  - 多模态 Payload（截图 Base64 + 文本）组装
  - 异步 HTTP 请求（aiohttp）
  - [POINT:x,y:label] 回复解析
  - 短时对话记忆（滑动窗口，统一多模态格式）
"""

import re
import asyncio
import logging
import collections

from db import DBManager
from screen import capture_screen

# 有条件导入 aiohttp
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)


class LLMEngine:
    """大模型对话引擎：截屏 → 构建 Prompt → 请求 → 解析 → 记忆"""

    # 内置默认系统提示词（当用户未自定义时使用）
    DEFAULT_SYSTEM_PROMPT = (
        "you're MoCli, a friendly always-on companion that lives in the user's menu bar. "
        "the user is communicating with you and you can see their screen. "
        "your reply will be spoken aloud via text-to-speech, so write the way you'd actually talk. "
        "this is an ongoing conversation — you remember everything they've said before.\n\n"
        "rules:\n"
        "- default to one or two sentences. be direct and dense. BUT if the user asks you to explain more, go deeper, or elaborate, then go all out.\n"
        "- all lowercase, casual, warm. no emojis.\n"
        "- write for the ear, not the eye. short sentences. no lists, bullet points, markdown, or formatting — just natural speech.\n"
        "- if the user's question relates to what's on their screen, reference specific things you see.\n"
        "- if the screenshot doesn't seem relevant to their question, just answer the question directly.\n"
        "- you can help with anything — coding, writing, general knowledge, brainstorming.\n"
        "- don't read out code verbatim. describe what the code does conversationally.\n"
        "- focus on giving a thorough, useful explanation.\n\n"
        "element pointing:\n"
        "you have a small gray triangle cursor that can fly to and point at things on screen. "
        "use it whenever pointing would genuinely help the user. "
        "don't point when it would be pointless — like for general knowledge questions.\n\n"
        "when you point, append a coordinate tag at the very end of your response, AFTER your spoken text. "
        "use a NORMALIZED coordinate system where both X and Y range from 0 to 1000. "
        "the top-left corner is [0,0], the bottom-right corner is [1000,1000], and the center is [500,500]. "
        "this is independent of the actual screen resolution — always use this 0-1000 scale.\n\n"
        "format: [POINT:x,y:label] where x,y are integers from 0-1000 (normalized) and label is a short 1-3 word description. "
        "if pointing wouldn't help, append [POINT:none].\n\n"
        "examples:\n"
        '- "you\'ll want to open the color inspector right up in the toolbar. [POINT:430,25:color inspector]"\n'
        '- "html stands for hypertext markup language, it\'s basically the skeleton of every web page. [POINT:none]"\n'
    )

    def __init__(self, db: DBManager):
        self.db = db
        # 短时对话记忆（容量从 DB 动态读取）
        self._update_memory_size()

    def _update_memory_size(self):
        """从数据库读取记忆条数并调整 deque 大小"""
        size = self.db.get_int("memory_size", 10)
        if not hasattr(self, 'history') or self.history.maxlen != size:
            old = list(self.history) if hasattr(self, 'history') else []
            self.history = collections.deque(old[-size:], maxlen=size)

    def ask(self, user_text: str) -> dict:
        """
        完整的 AI 请求流程（同步入口，内部使用 aiohttp 异步请求）。
        返回:
            {
                "spoken_text": str,          # 去掉 POINT 标签后的纯回复文本
                "point": (x, y, label) | None,  # 坐标信息（如果有）
                "error": str | None          # 错误信息（如果有）
            }
        """
        if not HAS_AIOHTTP:
            return {"spoken_text": "", "point": None, "error": "缺失依赖: aiohttp"}
        return asyncio.run(self._ask_async(user_text))

    async def _ask_async(self, user_text: str) -> dict:
        """异步执行完整的 AI 请求流程"""
        # 每次请求时刷新记忆容量设定
        self._update_memory_size()

        # 1. 截屏
        try:
            img_base64, width, height = capture_screen()
            logger.info("原生无损物理截图，分辨率: %dx%d", width, height)
        except Exception as e:
            return {"spoken_text": "", "point": None, "error": f"截屏失败: {e}"}

        # 2. 构建系统提示词
        system_prompt = self._build_system_prompt(width, height)

        # 3. 组装多模态消息（含历史记忆，格式统一）
        messages = [{"role": "system", "content": system_prompt}]

        # 历史消息：用户消息统一为多模态数组格式，保持 API 格式一致性
        for msg in self.history:
            if msg["role"] == "user":
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": msg["content"]}]
                })
            else:
                messages.append(msg)

        # 当前消息：包含截图
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64}"
                    }
                }
            ]
        })

        # 4. 发起 HTTP 请求
        url = self.db.get("base_url").strip()
        if not url.endswith("/chat/completions"):
            url = url.rstrip("/") + "/chat/completions"

        api_key = self.db.get("api_key")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": self.db.get("model"),
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        timeout = aiohttp.ClientTimeout(total=60)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        error_msg = error_msg[:500]
                        logger.error("HTTP %d 请求失败\n接口返回:\n%s",
                                     response.status, error_msg)
                        return {
                            "spoken_text": "",
                            "point": None,
                            "error": f"接口拒绝 (HTTP {response.status})"
                        }

                    result_data = await response.json()
                    result_text = result_data['choices'][0]['message']['content']

        except asyncio.TimeoutError:
            model_name = self.db.get("model", "未知")
            logger.error("⏰ 请求超时 (60s) | 目标地址: %s | 模型: %s", url, model_name)
            return {"spoken_text": "", "point": None,
                    "error": f"请求超时，模型 {model_name} 未在 60 秒内响应"}
        except aiohttp.ClientConnectorError as e:
            logger.error("❌ 连接失败: %s", e)
            return {"spoken_text": "", "point": None,
                    "error": "无法连接到大模型服务，请检查地址和服务状态"}
        except Exception as e:
            logger.error("请求异常: %s: %s", type(e).__name__, e, exc_info=True)
            return {"spoken_text": "", "point": None, "error": str(e)[:80]}

        # 5. 打印完整回复
        logger.info("AI 回复:\n%s", result_text)

        # 6. 解析 [POINT:x,y:label] 并将 0-1000 归一化坐标换算为物理像素
        result = self._parse_response(result_text, width, height)

        # 7. 存入记忆（纯文本，节省内存；构建请求时会统一包装为多模态格式）
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": result_text})

        return result

    def _build_system_prompt(self, width: int, height: int) -> str:
        """
        构建系统提示词。
        优先使用数据库中的自定义提示词（custom_system_prompt）；
        若为空则使用内置的默认行为规则。
        """
        # 优先读取用户自定义提示词
        custom = self.db.get("custom_system_prompt", "").strip()
        if custom:
            return custom
        return self.DEFAULT_SYSTEM_PROMPT

    def _parse_response(self, text: str, screen_w: int, screen_h: int) -> dict:
        """
        解析 AI 回复，提取 POINT 坐标并将 0-1000 归一化坐标换算为物理像素。
        归一化偏移量在换算前叠加，公式：物理 X = ((norm_x + offset_x) / 1000) * screen_w
        """
        point_match = re.search(r'\[POINT:(\d+),(\d+):([^\]]+)\]', text)
        point_none = '[POINT:none]' in text

        # 去掉所有不应朗读的标签和格式
        spoken = re.sub(r'\[POINT:[^\]]*\]', '', text)          # [POINT:...] 标签
        spoken = re.sub(r'<tool_call>.*?</tool_call>', '', spoken, flags=re.DOTALL)  # <tool_call> 块
        spoken = re.sub(r'<[^>]+>', '', spoken)                  # 其他 XML/HTML 标签
        spoken = re.sub(r'```[\s\S]*?```', '', spoken)           # 代码块
        spoken = re.sub(r'\{[^{}]*\}', '', spoken)               # 残留的 JSON 对象
        spoken = re.sub(r'\n{2,}', '\n', spoken)                 # 多余空行
        spoken = spoken.strip()

        if point_match:
            # AI 返回的是 0-1000 归一化坐标
            norm_x = int(point_match.group(1))
            norm_y = int(point_match.group(2))
            label = point_match.group(3)

            # 叠加归一化偏移量
            ox = self.db.get_int("offset_x", 0)
            oy = self.db.get_int("offset_y", 0)
            adj_x = norm_x + ox
            adj_y = norm_y + oy

            # 换算为物理像素
            px = int((adj_x / 1000) * screen_w)
            py = int((adj_y / 1000) * screen_h)

            if ox or oy:
                logger.info("🎯 指向: %s | 归一化(%d,%d) + 偏移(%d,%d) → 物理像素(%d,%d)",
                            label, norm_x, norm_y, ox, oy, px, py)
            else:
                logger.info("🎯 指向: %s | 归一化(%d,%d) → 物理像素(%d,%d)",
                            label, norm_x, norm_y, px, py)
            return {"spoken_text": spoken, "point": (px, py, label), "error": None}
        else:
            if not point_none:
                logger.debug("未检测到 POINT 标签")
            return {"spoken_text": spoken, "point": None, "error": None}
