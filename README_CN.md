<div align="right">
  <a href="./README.md">English</a> | <strong>简体中文</strong>
</div>

<p align="center">
  <img src="static/mocli-logo.svg" alt="MoCli Logo" width="120" />
</p>

<h1 align="center">MoCli</h1>
<p align="center"><strong>AI‑Powered Desktop Companion with Visual Pointing</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows" />
  <img src="https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt" />
  <img src="https://img.shields.io/badge/license-CC_BY--NC_4.0-orange?logo=creative-commons&logoColor=white" />
</p>

---

## 📖 简介

**MoCli** 是一个运行在 Windows 桌面上的 AI 伴侣助手。它以一个优雅的**三角形光标**驻留在屏幕上，通过语音唤醒或F10唤醒与用户交互。

MoCli 能看到你的屏幕、听到你的声音、理解你的意图，并用自然语言回答问题——还能精准地**将光标飞向屏幕上的任何元素**来指引你。

### ✨ 核心能力

- 🎯 **全局多航点解说巡航** — 打破单点往返限制！结合 VLM 界面分析与 TTS 波形时间轴，三角形光标能在执行教学步骤时，连续横穿多个坐标节点悬停并同步配以动态双轨（头衔/发言）滚动字幕，提供演说级的演示指南。
- 🗣️ **双模触发侦听机制** — 支持"贾维斯"全局自由声空唤醒，同时挂载 F10 物理按键强力录音推按对讲阻断（Push-To-Talk）。
- 🎤 **端到端离线隐私引擎 (STT)** — 采用 SenseVoice 中英双语离线推理识别，不上传私人对话。
- 🔊 **流式拟态发音 (TTS)** — 深入对接流式请求，音频下载与 QObject 动作队列紧密嵌合并具备字级预估挂起降级策略。
- 🌀 **情绪拟态渲染** — 聆听时绿色呼吸圆球，思考时紫色脑电波频段，待机时静默三角。
- ⚙️ **Win11 Fluent 设置舱** — 极具质感的 Fluent Design 三栏设置台，提供真机屏幕映射雷达和偏移矩阵矫正实验坪。

---

## 🏗️ 项目架构

MoCli 采用**模块化架构**，每个文件职责单一、松耦合：

```
MoCli/
├── main.py          # 程序入口 — 模块组装、信号编排、日志配置
├── db.py            # 配置管理 — SQLite 线程安全单例
├── voice.py         # 语音管理 — VoiceManager + 信号桥
├── settings.py      # 设置面板 — Win11 Fluent Design UI
├── tray.py          # 系统托盘 — 图标与右键菜单
├── utils.py         # 工具函数 — 资源路径、SVG 渲染、DPI 缩放
├── triangle.py      # 三角形光标 — 弹簧物理跟随 + 飞行动画 + 呼吸状态
├── screen.py        # 屏幕截图 — 无损物理像素截屏 + Base64 编码
├── llm.py           # 大模型引擎 — Prompt 构建 + 多模态请求 + 坐标解析
├── wakeup.py        # 语音唤醒 — sherpa-onnx KWS 关键词检测
├── stt.py           # 语音识别 — SenseVoice 离线推理 + WebRTC VAD
├── tts.py           # 语音合成 — aiohttp 异步流式 PCM 播放
├── static/          # 静态资源 — SVG 图标、ICO、PNG
├── pyproject.toml   # 项目配置与依赖
└── mocli.db         # SQLite 配置数据库（自动生成）
```

实时语音合成可以查看 https://github.com/llrrdb/Qwen3-TTS-X 这个项目

### 数据流向

```
语音唤醒 ──→ STT识别 ──→ 【全局调度】 ──→ 截屏+系统Prompt组装 ──→ VLM推理
                                                                   │
    ┌───────────────────────────┬──────────────────────────────────┘
    │                           ↓
    │           TTS流水线处理引擎 (异步多模态解析管线)
    │                  ↓                 ↓
    │          (检测到文字)      (检测到 P_POINT 坐标)
    │                  │                 │
如果无声则等待   调用扬声器并弹气泡   派发跨线程信号控制抛物线位移
```

---

## 🚀 快速开始

### 环境要求

| 项目     | 要求                                                       |
| -------- | ---------------------------------------------------------- |
| 操作系统 | Windows 10 / 11                                            |
| Python   | 3.11 或更高版本                                            |
| VLM 服务 | 任何兼容 OpenAI API 的视觉语言模型（如 LM Studio、Ollama） |
| TTS 服务 | 本地 TTS HTTP API（可选，如 Qwen3-TTS）                    |
| 麦克风   | 支持 16kHz 采样的音频输入设备（语音功能需要）              |

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/llrrdb/MoCli.git
cd MoCli

# 2. 创建并激活虚拟环境（推荐使用 uv）
uv venv --python 3.11
.venv\Scripts\activate

# 3. 安装依赖
uv sync

# 4. 下载语音模型（语音功能需要）
# KWS 唤醒模型
# 将 sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01 目录放在项目根目录
# STT 识别模型
# 将 sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17 目录放在项目根目录

# 5. 启动
python main.py
```

> **注意**：首次运行会自动创建 `mocli.db` 配置数据库。语音模型目录不存在时，程序会退化为纯文本模式。

---

## ⚙️ 配置说明

所有配置通过**系统托盘 → 右键 → 设置**进入 Win11 风格的设置面板管理。

### 🧠 大模型 Tab

| 配置项   | 说明         | 默认值                                      |
| -------- | ------------ | ------------------------------------------- |
| Base URL | VLM API 端点 | `http://127.0.0.1:1234/v1/chat/completions` |
| 模型名称 | 模型标识符   | `qwen2.5-vl-7b`                             |
| API Key  | 认证密钥     | `lm-studio`                                 |

### 🗣️ 语音 Tab

| 配置项       | 说明        | 默认值                                  |
| ------------ | ----------- | --------------------------------------- |
| 启用语音唤醒 | KWS 开关    | ✅ 开启                                 |
| 唤醒词       | 触发词      | `贾维斯`                                |
| 启用语音回复 | TTS 开关    | ✅ 开启                                 |
| TTS 服务地址 | TTS API URL | `http://localhost:8100/v1/audio/speech` |
| TTS 模型     | TTS 模型名  | `model-base`                            |

### ⚙️ 高级 Tab

| 配置项       | 说明                                                 |
| ------------ | ---------------------------------------------------- |
| 实时光标位置 | 显示鼠标当前物理像素坐标 (50ms 刷新)                 |
| 定点测试     | 输入归一化坐标 (0-1000) 测试光标飞行精度，停留 15 秒 |
| 全局偏移量   | 归一化偏移补偿 (0-1000)，应用于所有 AI 指向动作      |
| 对话记忆     | 滑动条调节短时记忆条数 (2-50)                        |
| 系统提示词   | 预设 Prompt 可修改                                   |

---

## 🎯 视觉定位系统

MoCli 使用 **0-1000 归一化坐标系** 进行视觉定位，这是当前主流 VLM 最擅长的定位方式：

```
┌──────────────────────────┐
│ (0,0)          (1000,0)  │
│                          │
│        (500,500)         │  ← 屏幕正中央
│                          │
│ (0,1000)      (1000,1000)│
└──────────────────────────┘
```

### 换算公式

```
物理像素 X = ((归一化X + 偏移X) / 1000) × 屏幕宽度
物理像素 Y = ((归一化Y + 偏移Y) / 1000) × 屏幕高度
```

**示例**：屏幕 2560×1600，AI 返回 `[POINT:500,500:目标]`，偏移量 (0,0)
→ 物理坐标 = (1280, 800) = 屏幕正中央 ✅

### 支持的模型

| 模型                 | 归一化坐标支持          |
| -------------------- | ----------------------- |
| Claude 3.5 Sonnet    | ⭐ 官方推荐 0-1000      |
| Gemini 1.5 Pro       | ⭐ 原生支持             |
| Qwen-VL 系列         | ✅ 训练数据含归一化标注 |
| 其他 OpenAI 兼容 VLM | ✅ 通过 Prompt 引导     |

---

## 🎨 光标状态可视化

三角形光标会根据 MoCli 的工作状态自动变换形状和颜色：

| 状态     | 形状      | 颜色           | 动效                  |
| -------- | --------- | -------------- | --------------------- |
| 待机     | 🔺 三角形 | 暗灰 `#282C34` | 弹簧跟随鼠标          |
| 聆听中   | 🟢 圆形   | 绿色 `#00DC64` | 呼吸缩放 + 透明度脉动 |
| 思考中   | 🟣 圆形   | 紫色 `#A032FF` | 呼吸缩放 + 透明度脉动 |
| AI 飞行  | 🔺 三角形 | 青色 `#00C8FF` | InOutQuad 缓动飞行    |
| 文本输入 | 🔺 三角形 | 橙色 `#FFAA00` | 静止                  |

### 🛠️ 开发者自定义

光标的物理参数和颜色直接在 [`triangle.py`](triangle.py) 第 95–108 行硬编码，修改后需重启程序生效：

```python
# ─── 文件: triangle.py, TriangleCursor.__init__() ───

# 弹簧物理参数（基于 SwiftUI .spring(response, dampingFraction) 模型）
self._spring_response      = 0.4    # 弹簧自然周期（秒）
                                     # 越小越灵敏：0.15=极紧 | 0.3=灵敏 | 0.5=平衡 | 0.8=慢悠

self._damping_fraction     = 0.6    # 阻尼比
                                     # <1=有弹性回弹：0.4=弹跃 | 0.6=平衡 | 1.0=无回弹

self._opacity              = 0.9    # 整体透明度 (0.0~1.0)

# 各状态颜色 — 格式 QColor(R, G, B)
self._color_idle           = QColor(40, 44, 52)      # 待机（暗灰）
self._color_ai             = QColor(0, 200, 255)     # AI 飞行指向（青色）
self._color_typing         = QColor(255, 170, 0)     # 文本输入中（橙色）
self._color_listening      = QColor(0, 220, 100)     # 聆听中（绿色）
self._color_thinking       = QColor(160, 50, 255)    # 思考推理中（紫色）
```

---

## 📁 语音模型目录结构

```
MoCli/
├── sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01/
│   ├── encoder-epoch-99-avg-1-chunk-16-left-64.onnx
│   ├── decoder-epoch-99-avg-1-chunk-16-left-64.onnx
│   ├── joiner-epoch-99-avg-1-chunk-16-left-64.onnx
│   └── tokens.txt
│
└── sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/
    ├── model.int8.onnx
    └── tokens.txt
```

> 模型可从 [sherpa-onnx 官方仓库](https://github.com/k2-fsa/sherpa-onnx) 获取。

---

## 🔧 技术细节

### 并发模型

MoCli 采用 **方案 A：共享 asyncio 事件循环**。`wakeup`、`stt`、`tts` 三个子系统在同一个后台线程的 asyncio 循环中运行，通过 `asyncio.Queue` 共享音频数据，降低线程切换开销。

### DPI 处理

强制设置环境变量 `QT_AUTO_SCREEN_SCALE_FACTOR=0`，确保截屏坐标与 Qt 窗口坐标 1:1 对齐，避免高 DPI 屏幕下的偏移。

### 跨线程安全

所有后台线程（AI 请求、语音引擎）通过 `pyqtSignal` 信号桥与 Qt 主线程通信，避免直接操作 Widget 导致的线程死锁。数据库层 (`DBManager`) 使用 `threading.Lock` 保护所有读写操作。

### 配置持久化

使用 SQLite 键值对数据库 (`mocli.db`)，采用 WAL 模式优化并发性能，所有配置修改即时生效，无需重启。

---

## 📋 依赖清单

| 包名        | 用途                          |
| ----------- | ----------------------------- |
| PyQt6       | GUI 框架、系统托盘、动画引擎  |
| aiohttp     | VLM + TTS 异步 HTTP 请求      |
| Pillow      | 屏幕截图与图像编码            |
| numpy       | 音频数据矩阵运算              |
| PyAudio     | 麦克风采集与扬声器播放        |
| sherpa-onnx | KWS 语音唤醒 + SenseVoice STT |
| webrtcvad   | 语音活动端点检测 (VAD)        |

---

## 🐛 常见问题

<details>
<summary><strong>Q: 启动后没有三角形光标？</strong></summary>

确保以**管理员权限**运行终端。MoCli 需要系统级权限来创建置顶透明窗口。

</details>

<details>
<summary><strong>Q: 语音唤醒不工作？</strong></summary>

1. 检查麦克风设备是否被其他应用占用
2. 确认 KWS 模型目录 `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01` 存在
3. 检查设置面板中"启用语音唤醒"是否开启
</details>

<details>
<summary><strong>Q: TTS 没有声音？</strong></summary>

1. 确认本地 TTS 服务已启动并监听正确端口
2. 在设置 → 语音 Tab 中检查 TTS 服务地址和模型名
3. 确认"启用语音回复"开关已开启
</details>

<details>
<summary><strong>Q: 光标指向位置不准确？</strong></summary>

1. 在设置 → 高级 Tab 中使用**定点测试**验证精度（输入 500,500 应飞向屏幕正中央）
2. 如果存在系统性偏移，调整**全局偏移量**进行补偿
3. 确保没有使用 Windows 的显示缩放（推荐 100%）
</details>

<details>
<summary><strong>Q: webrtcvad 安装失败？</strong></summary>

确保 `setuptools` 版本低于 71：

```bash
pip install "setuptools<71"
pip install webrtcvad
```

</details>

---

<a href="https://star-history.com/#llrrdb/MoCli&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=llrrdb/MoCli&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=llrrdb/MoCli&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=llrrdb/MoCli&type=Date" />
 </picture>
</a>

## 开源协议

本项目采用 [CC BY-NC 4.0 (知识共享署名-非商业性使用 4.0 国际)](https://creativecommons.org/licenses/by-nc/4.0/deed.zh) 协议授权。

### ⚠️ 特别说明：

1. **个人/教育/非营利使用**：完全免费，无需申请授权。
2. **商业使用**：禁止将本项目及其衍生版本用于任何形式的商业盈利目的（包括但不限于付费软件集成、企业内部收费工具、有偿技术服务等）。
3. **商业授权**：若需在商业环境中使用或获得豁免非商业限制的授权，请联系作者：[邮箱：lr298977887@gmail.com，微信：lllrrr0807]。
