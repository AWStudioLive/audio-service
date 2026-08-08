# 🎙️ Whisper Voice Engine Service

<p align="center">
  <b>English</b> | <a href="./docs/README.ru.md">Русский</a>
</p>

---

High-performance asynchronous microservice for real-time speech recognition and command processing using **faster-whisper** (CTranslate2) and **WebSockets**. Designed to integrate voice input capabilities into the VS Code extension.

## 🚀 Features

- **Hardware Acceleration:** Automatic detection and setup of CUDA GPU (NVIDIA) with automatic fallback to CPU.
- **Windows CUDA Auto-Configuration:** Automatically registers CUDA DLL paths from `pip` site-packages.
- **Flexible Processing Modes:** Supports `MANUAL`, `CONTINUOUS`, and `BOUNDED` voice input workflows.
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
    └── README.ru.md    # Documentation (Russian)