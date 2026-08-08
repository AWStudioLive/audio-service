# 🎙️ Whisper Voice Engine Service

<p align="center">
  <b>English</b> | <a href="./docs/README.ru.md">Русский</a>
</p>

---

High-performance asynchronous microservice for real-time speech recognition and command processing using **faster-whisper** (CTranslate2) and **WebSockets**. Designed to integrate voice input capabilities into the VS Code extension.

## 🚀 Features

- **Hardware Acceleration:** Automatic detection and setup of CUDA GPU (NVIDIA) with automatic fallback to CPU.
- **Windows CUDA Auto-Configuration:** Automatically registers CUDA DLL paths from `pip` site-packages.
- **Flexible Processing Modes:** Supports `MANUAL` and `AUTO` voice input workflows.
- **Smart Trigger Detection:** Customizable activation, submission, and stop triggers with punctuation normalization.
- **WebSocket Protocol:** Asynchronous JSON-based event-driven communication.
- **Technical Vocabulary Prompting:** Context injection for enhanced accuracy on developer terms and code syntax.

## 📁 Project Structure

```text
.
├── main.py          # WebSocket server, audio streaming loop, and Whisper engine
├── config.py        # Service configurations, parameters, and defaults
├── enums.py         # Enums for Whisper model sizes and voice modes
├── requirements.txt # Python package dependencies
├── pyproject.toml   # Project metadata and dependencies
├── README.md        # Documentation (English)
└── docs/
    └── README.ru.md # Documentation (Russian)
```

## 📋 Requirements

- **Python:** `>= 3.12, < 3.13`
- **NVIDIA GPU:** Recommended for CUDA acceleration (Pascal architecture GTX 1050 or higher)
- **Audio Input:** Working microphone configured as the default system capture device

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AWStudioLive/audio-service.git
   cd audio-service
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   
   # Windows:
   .venv\Scripts\activate
   
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🚦 Usage

Start the WebSocket server:

```bash
python main.py
```

The server will start listening on `ws://localhost:8765`.

## 🔄 Engine Voice Modes

1. **`manual`**: Recording starts on `START` action and transcribes audio once `STOP` action is received.
2. **`auto` (Default)**: Interactive voice sessions. Listens for start triggers to open a session (`VOICE_SESSION_STARTED`), streams partial transcriptions while active (`VOICE_SESSION_PARTIAL`), pushes accumulated text on submit triggers (`VOICE_SESSION_SUBMIT`), and closes the session on stop triggers (`VOICE_SESSION_ENDED`).

## 📡 WebSocket API Specification

### Incoming Actions (Client $\rightarrow$ Server)

- **Set Mode & Custom Triggers:**
  ```json
  {
    "action": "SET_MODE",
    "mode": "auto",
    "triggers_start": ["computer", "listen"],
    "triggers_stop": ["stop", "done"],
    "triggers_submit": ["send", "submit"]
  }
  ```
- **Start Listening / Recording:**
  ```json
  { "action": "START" }
  ```
- **Stop Listening / Mute:**
  ```json
  { "action": "STOP" }
  ```

### Outgoing Events (Server $\rightarrow$ Client)

- **`MANUAL_RESULT`**: Transcribed result after `STOP` in `manual` mode.
- **`VOICE_SESSION_STARTED`**: Session initiated in `auto` mode.
- **`VOICE_SESSION_PARTIAL`**: Incremental text updates during an active session.
- **`VOICE_SESSION_SUBMIT`**: Text submission triggered without ending the session.
- **`VOICE_SESSION_ENDED`**: Session closed via stop trigger.

## 📄 License

MIT