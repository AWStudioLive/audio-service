# 🎙️ Whisper Voice Engine Service

<p align="center">
  <b>English</b> | <a href="./docs/README.ru.md">Русский</a>
</p>

---

High-performance asynchronous microservice for real-time speech recognition and voice command routing using **faster-whisper** (CTranslate2) and **WebSockets**. Designed to integrate voice input and automated command execution into VS Code extensions and OS desktop agents.

## 🚀 Features

- **Hardware Acceleration:** Automatic detection and setup of CUDA GPU (NVIDIA) with fallback to CPU.
- **Windows CUDA Auto-Configuration:** Automatically registers CUDA DLL paths from `pip` site-packages.
- **Flexible Processing Modes:** Supports `MANUAL` (Push-to-Talk), `AUTO` (Session Dictation), and `COMMAND` (Dedicated Command Execution) modes.
- **Voice Command Routing:** Evaluates spoken triggers against a command registry and dispatches `VOICE_COMMAND_EXECUTE` events targeted to VS Code commands or external Desktop Agents via HTTP/REST.
- **Smart Trigger Detection:** Customizable activation, submission, clear, and stop triggers with regex normalization.
- **WebSocket Protocol:** Event-driven JSON communication over WebSockets.
- **Technical Vocabulary Prompting:** Context injection via `TECHNICAL_PROMPT` to enhance accuracy for code syntax and command phrases.

## 📁 Project Structure

```text
.
├── main.py          # WebSocket server, audio streaming loop, and Whisper transcription engine
├── config.py        # Service configurations, parameters, triggers, and command registry
├── enums.py         # Enums for Whisper models, voice modes, and command targets
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
   git clone [https://github.com/AWStudioLive/audio-service.git](https://github.com/AWStudioLive/audio-service.git)
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

1. **`manual`**: Push-to-Talk mode. Recording starts on `START` action and transcribes accumulated audio once `STOP` action is received.
2. **`auto` (Default)**: Interactive dictation with ambient command detection. Listens for start triggers to open a session (`VOICE_SESSION_STARTED`), streams partial transcriptions (`VOICE_SESSION_PARTIAL`), submits accumulated text on submit triggers (`VOICE_SESSION_SUBMIT`), and closes the session on stop triggers (`VOICE_SESSION_ENDED`). While paused, it routes voice commands.
3. **`command`**: Dedicated command mode. Disables text accumulation for chat/editor input and strictly evaluates incoming audio against `DEFAULT_COMMAND_TRIGGERS`.

## ⚙️ Voice Command System

Commands are defined in `config.py` under `DEFAULT_COMMAND_TRIGGERS` and mapped to targets defined in `enums.py` (`VoiceCommandTarget`):

* **`vscode`**: Targets VS Code extension commands (e.g., `editor.action.formatDocument`, `extension.executeRedirect`).
* **`desktop_agent`**: Targets an OS desktop agent service via HTTP endpoints (e.g., opening browser or terminal).

```python
DEFAULT_COMMAND_TRIGGERS = {
    "FORMAT_CODE": {
        "target": VoiceCommandTarget.VSCODE,
        "action": "editor.action.formatDocument",
        "triggers": [
            "отформатируй код", "отформатирую код", "форматируй код", "форматирование"
        ],
    },
    "OPEN_BROWSER": {
        "target": VoiceCommandTarget.DESKTOP_AGENT,
        "action": "open_browser",
        "triggers": ["открой браузер", "запусти браузер", "браузер"],
    },
}
```

## 📡 WebSocket API Specification

### Incoming Actions (Client -> Server)

- **Set Mode & Custom Triggers:**
  ```json
  {
    "action": "SET_MODE",
    "mode": "auto",
    "triggers_start": ["эни", "start"],
    "triggers_stop": ["стоп", "stop"],
    "triggers_submit": ["отправь", "submit"],
    "triggers_clear": ["очисти", "reset"]
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

### Outgoing Events (Server -> Client)

- **`MANUAL_RESULT`**: Transcribed text after `STOP` in `manual` mode.
- **`VOICE_SESSION_STARTED`**: Session opened in `auto` mode.
- **`VOICE_SESSION_PARTIAL`**: Incremental text updates during an active dictation session.
- **`VOICE_SESSION_SUBMIT`**: Text submission triggered by keyword.
- **`VOICE_SESSION_ENDED`**: Session closed via stop trigger.
- **`VOICE_COMMAND_EXECUTE`**: Dispatched when a command trigger is matched:
  ```json
  {
    "type": "VOICE_COMMAND_EXECUTE",
    "command_id": "FORMAT_CODE",
    "phrase": "отформатируй код",
    "payload": {
      "target": {
        "name": "vscode",
        "address": "vscode://command",
        "method": "EXECUTE"
      },
      "action": "editor.action.formatDocument"
    }
  }
  ```

## 📄 License

MIT