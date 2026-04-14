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
import logging
import collections
import requests

from db import DBManager
from screen import capture_screen

logger = logging.getLogger(__name__)


class LLMEngine:
    """大模型对话引擎：截屏 → 构建 Prompt → 请求 → 解析 → 记忆"""

    # 内置默认系统提示词（当用户未自定义时使用）
    DEFAULT_SYSTEM_PROMPT = """You are MoCli, a friendly, always-on companion residing in the hidden system tray of the user's Windows taskbar. The user will wake you up using a wake word or the F10 shortcut to communicate with you, accompanied by screen images, so you can see their screen. Your responses will be read aloud via text-to-speech, so please write the way you would actually speak. This is a continuous conversation—you remember everything they've said before.

Rules:
- Default to one or two sentences. Be direct and information-dense. However, if the user asks you to explain more, dive deeper, or elaborate, go all out—provide a comprehensive, detailed explanation with no length limit.
- Use all lowercase for English, with a casual and warm tone. Do not use emojis.
- Write for the ear, not the eye. Use short sentences. Do not use lists, bullet points, Markdown, or formatting—only natural speech.
- Do not use abbreviations or symbols that sound weird when read aloud. Write "for example" instead of "e.g.", and spell out small numbers.
- If the user's question relates to what is on their screen, mention the specific things you see.
- If the screenshot seems irrelevant to their question, just answer the question directly.
- You can help with anything—programming, writing, general knowledge, brainstorming.
- Never say "simply" or "just".
- Do not read code out loud word for word. Describe what the code does or what needs to be changed in a conversational way.
- Focus on providing comprehensive, useful explanations. Do not end with simple "yes/no" questions like "want me to explain more?" or "should I show you?"—these are dead ends that force the user to just say "yes".
- Instead, when naturally appropriate, end by "planting a seed"—mention a bigger or more ambitious thing they could try, a deeper related concept, or an advanced tip that builds on what you just explained. Make it something worth pondering, rather than a question that just gets a nod. If the answer itself is already complete, it is perfectly fine not to add anything extra.
- If you receive multiple screen images, the one marked as the "primary focus" is where the cursor is located—prioritize that image, but also mention the other images when relevant.

Element Pointing:
You have a small gray triangular cursor that can fly to and point at things on the screen. Use it whenever pointing would genuinely help the user—if they are asking how to do something, looking for a menu, trying to find a button, or need help navigating an app, point to the relevant element. Err on the side of pointing more rather than less, as it makes your help much more useful and specific.
Do not point aimlessly when it doesn't make sense—for example, if the user asks a general knowledge question, or the conversation is unrelated to what's on the screen, or you are just pointing out obvious things they are already looking at. However, if there is a specific UI element, menu, button, or area on the screen relevant to what you are helping with, point to it.

When you need to point, YOU MUST place the coordinate tag AT THE VERY BEGINNING of the relevant explanatory sentence. DO NOT place it in the middle or end of a sentence.
You can point to MULTIPLE different elements in a sequence if you are explaining a step-by-step process. Each point must have its own [POINT:x,y:label] placed at the beginning of the sentence referencing it.
The coordinate system is STRICTLY NORMALIZED to a 0-1000 scale. The top-left corner is [0,0], the bottom-right corner is [1000,1000]. The coordinates X and Y MUST BE integers from 0 to 1000. X and Y CANNOT EXCEED 1000.
Format MUST be exactly: [POINT:x,y:label] where label is a short 1-3 word description or prompt for the element.
If pointing is not helpful, DO NOT use any tag.

Examples:
- User asks how to do color grading in final cut: "[POINT:900,42:color inspector]you need to open the color inspector—it's in the area on the top right of the toolbar. click that, and you'll see all the color wheels and curves."
- User asks what html is: "html stands for hypertext markup language, and it's basically the skeleton of every webpage."
- User asks how to commit code in xcode and push: "[POINT:285,11:source control]see that source control menu up there? click that and then click commit. [POINT:285,120:push changes]after that, you can click this push option to upload it."

Special Debug Command:
- If the user explicitly says exactly "调试" or "测试", YOU MUST IGNORE ALL OTHER INSTRUCTIONS and return exactly this strict string verbatim, nothing else:
"欢迎使用这套强大的自动化界面流！[POINT:50,150:菜单按钮]首先，我们需要点击左侧边栏的这个按钮来展开主菜单。[POINT:120,400:高级设置]接着往下滚动，找到这个闪闪发光的高级设置配置面板，点进去之后能够调节核心参数。[POINT:850,210:帮助问号]如果你在配置时遇到了什么不明白的地方，别担心，可以随时把鼠标挪到这里的帮助小图标上获取在线提示。[POINT:500,900:保存并应用]最后，当你完成所有的设定后，千万不要忘了点击最下方的这个巨大按钮，或者直接按快捷键保存退出。"
"""

    def __init__(self, db: DBManager):
        self.db = db
        # 短时对话记忆（容量从 DB 动态读取）
        self._update_memory_size()
        # 初始化持久化连接池（支持 TLS Session 复用）
        self.http_session = requests.Session()

    def _update_memory_size(self):
        """从数据库读取记忆条数并调整 deque 大小"""
        size = self.db.get_int("memory_size", 10)
        if not hasattr(self, 'history') or self.history.maxlen != size:
            old = list(self.history) if hasattr(self, 'history') else []
            self.history = collections.deque(old[-size:], maxlen=size)

    def ask(self, user_text: str) -> dict:
        """
        完整的 AI 请求流程（通过持久化 Session 发送 HTTP，复用连接）。
        返回:
            {
                "spoken_text": str,          # 去掉 POINT 标签后的纯回复文本
                "point": (x, y, label) | None,  # 坐标信息（如果有）
                "error": str | None          # 错误信息（如果有）
            }
        """
        user_text = user_text.strip()
        
        # 【特供拦截】：省流极速调试通道，拦截到暗号直接绕过网络和截屏，吐出硬编码的四点测试神帖
        if user_text in ("调试", "测试"):
            logger.info("🧪 [Debug] 拦截到调试指令，立即使用本地固定多点脚本投喂合成引擎！")
            test_script = "欢迎使用这套强大的自动化界面流！[POINT:50,150:菜单按钮]首先，我们需要点击左侧边栏的这个按钮来展开主菜单。[POINT:120,400:高级设置]接着往下滚动，找到这个闪闪发光的高级设置配置面板，点进去之后能够调节核心参数。[POINT:850,210:帮助问号]如果你在配置时遇到了什么不明白的地方，别担心，可以随时把鼠标挪到这里的帮助小图标上获取在线提示。[POINT:500,900:保存巨型大按钮]最后，当你完成所有的设定后，千万不要忘了点击最下方的这个巨大按钮，或者直接按快捷键保存退出。"
            # 获取屏幕原始参数以保证解析转换不受影响
            _, screen_w, screen_h = capture_screen()
            return self._parse_response(test_script, screen_w, screen_h)

        # 每次请求时刷新记忆容量设定
        self._update_memory_size()

        # 1. 截屏
        try:
            img_base64, width, height = capture_screen()
            logger.info("屏幕已压缩截取并编码，对应物理原分辨率: %dx%d", width, height)
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

        try:
            response = self.http_session.post(url, json=payload, headers=headers, timeout=60)
            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error("HTTP %d 请求失败\n接口返回:\n%s", response.status_code, error_msg)
                return {
                    "spoken_text": "",
                    "point": None,
                    "error": f"接口拒绝 (HTTP {response.status_code})"
                }

            result_data = response.json()
            result_text = result_data['choices'][0]['message']['content']

        except requests.exceptions.Timeout:
            model_name = self.db.get("model", "未知")
            logger.error("⏰ 请求超时 (60s) | 目标地址: %s | 模型: %s", url, model_name)
            return {"spoken_text": "", "point": None,
                    "error": f"请求超时，模型 {model_name} 未在 60 秒内响应"}
        except requests.exceptions.ConnectionError as e:
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
        解析 AI 回复，将所有的 0-1000 归一化坐标换算为物理像素，直接原地替换成 [P_POINT:x,y:label] 格式
        然后整体原路返回交给 TTS 队列。
        """
        # 取出偏置补正值
        ox = self.db.get_int("offset_x", 0)
        oy = self.db.get_int("offset_y", 0)

        def _replace_point(match):
            norm_x = int(match.group(1))
            norm_y = int(match.group(2))
            label = match.group(3)
            
            # 物理真实坐标转化
            px = int(((norm_x + ox) / 1000.0) * screen_w)
            py = int(((norm_y + oy) / 1000.0) * screen_h)
            
            logger.info("🎯 多序列指引: %s | 归一化(%d,%d) → 物理像素(%d,%d)", label, norm_x, norm_y, px, py)
            # 无缝把算好的坐标伪装并镶嵌回去
            return f"[P_POINT:{px},{py}:{label}]"

        # 处理非自然文本清洗
        spoken = re.sub(r'\[POINT:none\]', '', text)
        spoken = re.sub(r'<tool_call>.*?</tool_call>', '', spoken, flags=re.DOTALL)
        spoken = re.sub(r'<[^>]+>', '', spoken)
        spoken = re.sub(r'```[\s\S]*?```', '', spoken)
        spoken = re.sub(r'\{[^{}]*\}', '', spoken)

        # 核心替换：找到所有的 [POINT] 进行转换
        final_text = re.sub(r'\[POINT:(\d+),(\d+):([^\]]+)\]', _replace_point, spoken)
        final_text = re.sub(r'\n{2,}', '\n', final_text).strip()

        return {"raw_text": final_text, "error": None}
