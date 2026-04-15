<div align="right">
  <strong>English</strong> | <a href="./README_CN.md">简体中文</a>
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

## 📖 Introduction

**MoCli** is an AI companion assistant running natively on the Windows desktop. It resides on your screen as an elegant **triangular cursor** and interacts with you via voice wake-up or by pressing the F10 key.

MoCli can see your screen, hear your voice, understand your intentions, and respond in natural language—it can even **fly its cursor precisely to any element on your screen** to guide you visually.

### ✨ Core Features

- 🎯 **Global Multi-Waypoint Guided Cruising** — Breaking the limits of single-point movement! Combining VLM UI analysis with TTS waveform timelines, the triangular cursor can hover across multiple coordinate nodes continuously. It synchronizes with dynamic dual-track (Title/Speech) scrolling subtitles, delivering presentation-level visual guides.
- 🗣️ **Dual-Mode Trigger & Listening** — Supports global hands-free voice wake-up ("Jarvis") and features a robust Push-To-Talk (PTT) interruption mechanism via the F10 physical key.
- 🎤 **End-to-End Offline Privacy Engine (STT)** — Utilizes SenseVoice for bilingual (EN/ZH) offline inference recognition, ensuring your private conversations are never uploaded.
- 🔊 **Streaming Mimetic Speech (TTS)** — Deeply integrated with streaming requests. Audio downloading is tightly coupled with the QObject action queue, featuring a character-level estimation and fallback suspension strategy.
- 🌀 **Emotional Mimetic Rendering** — Transforms into a breathing green sphere when listening, a purple brainwave band when thinking, and a silent triangle when idle.
- ⚙️ **Win11 Fluent Settings Cabin** — A highly textured three-column Fluent Design settings panel, offering a real-time screen mapping radar and an offset matrix calibration lab.

---

## 🏗️ Project Architecture

MoCli adopts a **modular architecture**, ensuring single responsibility and loose coupling for each file:

```text
MoCli/
├── main.py          # Entry Point — Module assembly, signal orchestration, logging
├── db.py            # Config Manager — Thread-safe SQLite singleton
├── voice.py         # Voice Manager — VoiceManager + Signal Bridge
├── settings.py      # Settings Panel — Win11 Fluent Design UI
├── tray.py          # System Tray — Icon and context menu
├── utils.py         # Utilities — Resource paths, SVG rendering, DPI scaling
├── triangle.py      # Triangle Cursor — Spring physics, flight animation, breathing states
├── screen.py        # Screen Capture — Lossless physical pixel capture + Base64 encoding
├── llm.py           # LLM Engine — Prompt building, multimodal requests, coordinate parsing
├── wakeup.py        # Voice Wake-up — sherpa-onnx KWS keyword detection
├── stt.py           # Speech-to-Text — SenseVoice offline inference + WebRTC VAD
├── tts.py           # Text-to-Speech — aiohttp async streaming PCM playback
├── static/          # Static Resources — SVG icons, ICO, PNG
├── pyproject.toml   # Project configuration and dependencies
└── mocli.db         # SQLite Config Database (auto-generated)
```

For real-time TTS synthesis, check out the [Qwen3-TTS-X](https://github.com/llrrdb/Qwen3-TTS-X) project.

### Data Flow

```text
Voice Wake-up ──→ STT Recognition ──→ [Global Dispatch] ──→ Screenshot + Prompt Assembly ──→ VLM Inference
                                                                       │
    ┌───────────────────────────────┬──────────────────────────────────┘
    │                               ↓
    │                TTS Pipeline Processing Engine (Async Multimodal Pipeline)
    │                      ↓                           ↓
    │               (Text Detected)             (P_POINT Detected)
    │                      │                           │
Wait if silent    Call speaker & popup bubble    Dispatch cross-thread signal for parabolic flight
```

---

## 🚀 Quick Start

### Prerequisites

| Component   | Requirement                                                                |
| ----------- | -------------------------------------------------------------------------- |
| OS          | Windows 10 / 11                                                            |
| Python      | 3.11 or higher                                                             |
| VLM Service | Any OpenAI API-compatible Vision-Language Model (e.g., LM Studio, Ollama)  |
| TTS Service | Local TTS HTTP API (Optional, e.g., Qwen3-TTS)                             |
| Microphone  | Audio input device supporting 16kHz sampling (required for voice features) |

### Installation

```bash
# 1. Clone the repository
git clone [https://github.com/llrrdb/MoCli.git](https://github.com/llrrdb/MoCli.git)
cd MoCli

# 2. Create and activate a virtual environment (uv is recommended)
uv venv --python 3.11
.venv\Scripts\activate

# 3. Install dependencies
uv sync

# 4. Download Voice Models (Required for voice features)
# KWS Wake-up Model:
# Place the `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01` directory in the project root.
# STT Recognition Model:
# Place the `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17` directory in the project root.

# 5. Run the application
python main.py
```

> **Note**: A `mocli.db` configuration database will be automatically created on the first run. If the voice model directories are missing, the program will gracefully degrade to text-only mode.

---

## ⚙️ Configuration

All configurations are managed through a Win11-style settings panel. Access it via **System Tray → Right Click → Settings**.

### 🧠 LLM Tab

| Setting    | Description        | Default Value                               |
| ---------- | ------------------ | ------------------------------------------- |
| Base URL   | VLM API Endpoint   | `http://127.0.0.1:1234/v1/chat/completions` |
| Model Name | Model Identifier   | `qwen2.5-vl-7b`                             |
| API Key    | Authentication Key | `lm-studio`                                 |

### 🗣️ Voice Tab

| Setting            | Description      | Default Value                           |
| ------------------ | ---------------- | --------------------------------------- |
| Enable Wake-up     | KWS Toggle       | ✅ Enabled                              |
| Wake Word          | Trigger Phrase   | `贾维斯` (Jarvis)                       |
| Enable Voice Reply | TTS Toggle       | ✅ Enabled                              |
| TTS URL            | TTS API Endpoint | `http://localhost:8100/v1/audio/speech` |
| TTS Model          | TTS Model Name   | `model-base`                            |

### ⚙️ Advanced Tab

| Setting         | Description                                                                 |
| --------------- | --------------------------------------------------------------------------- |
| Live Cursor Pos | Displays current physical pixel coordinates of the mouse (50ms refresh).    |
| Pointing Test   | Input normalized coords (0-1000) to test flight accuracy. Hovers for 15s.   |
| Global Offset   | Normalized offset compensation (0-1000) applied to all AI pointing actions. |
| Chat Memory     | Slider to adjust short-term memory history count (2-50).                    |
| System Prompt   | Customizable preset system instructions.                                    |

---

## 🎯 Visual Positioning System

MoCli uses a **0-1000 Normalized Coordinate System** for visual positioning, which aligns perfectly with how modern VLMs process spatial data:

```text
┌──────────────────────────┐
│ (0,0)          (1000,0)  │
│                          │
│        (500,500)         │  ← Screen Center
│                          │
│ (0,1000)      (1000,1000)│
└──────────────────────────┘
```

### Conversion Formula

```text
Physical Pixel X = ((Normalized X + Offset X) / 1000) × Screen Width
Physical Pixel Y = ((Normalized Y + Offset Y) / 1000) × Screen Height
```

**Example**: On a 2560×1600 screen, if the AI returns `[POINT:500,500:Target]` with a (0,0) offset:
→ Physical Coordinates = (1280, 800) = Exact center of the screen ✅

### Supported Models

| Model                        | Normalized Coordinate Support                    |
| ---------------------------- | ------------------------------------------------ |
| Claude 3.5 Sonnet            | ⭐ Officially recommended (0-1000)               |
| Gemini 1.5 Pro               | ⭐ Native support                                |
| Qwen-VL Series               | ✅ Training data includes normalized annotations |
| Other OpenAI-compatible VLMs | ✅ Achievable via System Prompt guidance         |

---

## 🎨 Cursor State Visualization

The triangular cursor dynamically changes shape and color based on MoCli's current working state:

| State     | Shape       | Color               | Animation                       |
| --------- | ----------- | ------------------- | ------------------------------- |
| Idle      | 🔺 Triangle | Dark Gray `#282C34` | Spring physics mouse follow     |
| Listening | 🟢 Circle   | Green `#00DC64`     | Breathing scale + Opacity pulse |
| Thinking  | 🟣 Circle   | Purple `#A032FF`    | Breathing scale + Opacity pulse |
| AI Flying | 🔺 Triangle | Cyan `#00C8FF`      | InOutQuad easing flight         |
| Typing    | 🔺 Triangle | Orange `#FFAA00`    | Static                          |

### 🛠️ Developer Customization

The physical parameters and colors of the cursor are hardcoded in [`triangle.py`](https://www.google.com/search?q=triangle.py) (Lines 95–108). A restart is required after modification:

```python
# ─── File: triangle.py, TriangleCursor.__init__() ───

# Spring physics parameters (based on SwiftUI .spring() model)
self._spring_response      = 0.4    # Spring natural period (seconds)
                                     # Lower = more responsive: 0.15=Snappy | 0.3=Agile | 0.5=Balanced | 0.8=Relaxed

self._damping_fraction     = 0.6    # Damping ratio
                                     # <1=Bouncy: 0.4=High Bounce | 0.6=Balanced | 1.0=No Bounce

self._opacity              = 0.9    # Overall opacity (0.0~1.0)

# Colors for different states — Format: QColor(R, G, B)
self._color_idle           = QColor(40, 44, 52)      # Idle (Dark Gray)
self._color_ai             = QColor(0, 200, 255)     # AI Pointing/Flying (Cyan)
self._color_typing         = QColor(255, 170, 0)     # Text input active (Orange)
self._color_listening      = QColor(0, 220, 100)     # Listening (Green)
self._color_thinking       = QColor(160, 50, 255)    # Thinking/Inferencing (Purple)
```

---

## 📁 Voice Model Directory Structure

```text
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

> Models can be downloaded from the official [sherpa-onnx repository](https://github.com/k2-fsa/sherpa-onnx).

---

## 🔧 Technical Details

### Concurrency Model

MoCli utilizes a **Shared asyncio Event Loop** strategy. The `wakeup`, `stt`, and `tts` subsystems run concurrently within the same background thread's asyncio loop, sharing audio data via `asyncio.Queue` to minimize thread-switching overhead.

### DPI Handling

The environment variable `QT_AUTO_SCREEN_SCALE_FACTOR=0` is strictly enforced. This ensures a 1:1 alignment between screenshot coordinates and Qt window coordinates, preventing offset issues on high-DPI displays.

### Cross-Thread Safety

All background threads (AI requests, voice engines) communicate with the Qt main thread exclusively via `pyqtSignal` bridges to prevent thread deadlocks caused by direct Widget manipulation. The database layer (`DBManager`) uses `threading.Lock` to secure all Read/Write operations.

### Configuration Persistence

Configurations are stored in an SQLite Key-Value database (`mocli.db`) operating in WAL mode to optimize concurrent performance. All settings changes take effect immediately without requiring a restart.

---

## 📋 Dependencies

| Package     | Purpose                                      |
| ----------- | -------------------------------------------- |
| PyQt6       | GUI Framework, System Tray, Animation Engine |
| aiohttp     | Async HTTP requests for VLM + TTS            |
| Pillow      | Screen capture and image encoding            |
| numpy       | Audio data matrix operations                 |
| PyAudio     | Microphone capture and speaker playback      |
| sherpa-onnx | KWS Voice Wake-up + SenseVoice STT           |
| webrtcvad   | Voice Activity Detection (VAD)               |

---

## 🐛 FAQ

\<details\>
\<summary\>\<strong\>Q: I don't see the triangle cursor after launching?\</strong\>\</summary\>

Make sure to run your terminal with **Administrator privileges**. MoCli requires system-level permissions to create top-level transparent overlay windows.

\</details\>

\<details\>
\<summary\>\<strong\>Q: Voice wake-up is not working?\</strong\>\</summary\>

1.  Check if your microphone is exclusively locked by another application.
2.  Ensure the KWS model directory `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01` exists in the root folder.
3.  Verify that "Enable Wake-up" is checked in the Settings panel.

\</details\>

\<details\>
\<summary\>\<strong\>Q: No sound from TTS?\</strong\>\</summary\>

1.  Confirm your local TTS service is running and listening on the correct port.
2.  Check the TTS URL and Model Name in the Settings → Voice Tab.
3.  Ensure the "Enable Voice Reply" toggle is switched on.

\</details\>

\<details\>
\<summary\>\<strong\>Q: The cursor points to the wrong location?\</strong\>\</summary\>

1.  Use the **Pointing Test** in the Advanced Settings tab (inputting `500,500` should fly exactly to the center of your screen).
2.  If there is a systematic offset, adjust the **Global Offset** to compensate.
3.  Ensure you are not using Windows Display Scaling (100% is highly recommended).

\</details\>

\<details\>
\<summary\>\<strong\>Q: Failed to install `webrtcvad`?\</strong\>\</summary\>

Ensure your `setuptools` version is below 71:

```bash
pip install "setuptools<71"
pip install webrtcvad
```

\</details\>

---

\<a href="https://star-history.com/\#llrrdb/MoCli\&Date"\>
\<picture\>
\<source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=llrrdb/MoCli\&type=Date\&theme=dark" /\>
\<source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=llrrdb/MoCli\&type=Date" /\>
\<img alt="Star History Chart" src="https://api.star-history.com/svg?repos=llrrdb/MoCli\&type=Date" /\>
\</picture\>
\</a\>

## License

This project is licensed under the [CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International)](https://creativecommons.org/licenses/by-nc/4.0/).

### ⚠️ Special Notes:

1.  **Personal / Educational / Non-Profit Use**: Completely free, no explicit authorization required.
2.  **Commercial Use**: It is strictly prohibited to use this project or its derivatives for any commercial or profit-driven purposes (including but not limited to paid software integration, internal enterprise tools, or paid technical services).
3.  **Commercial Licensing**: If you wish to use MoCli in a commercial environment or obtain an exemption from the non-commercial restriction, please contact the author: [Email: lr298977887@gmail.com, WeChat: lllrrr0807].
