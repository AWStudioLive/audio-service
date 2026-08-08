# config.py

import os
import sys

# Импортируем типы из enums
from enums import EngineVoiceMode, VoiceCommandTarget, WhisperModelSize

# --- Настройки сервера ---
WS_HOST = "localhost"
WS_PORT = 8765
WS_PING_INTERVAL = 20  # Интервал отправки ping-пакетов клиенту (в секундах)
WS_PING_TIMEOUT = 10   # Время ожидания pong-ответа перед закрытием сокета (в секундах)

# --- Параметры аудио и тайминги обработки ---
SAMPLE_RATE = 16000
CHANNELS = 1
BACKGROUND_LOOP_INTERVAL = 0.8  # Задержка фонового цикла опроса (в секундах)
MIN_AUDIO_DURATION_SEC = 2      # Минимальная длина аудиобуфера для отправки в Whisper (в секундах)

# --- Настройки Whisper ---
WHISPER_MODEL_NAME = WhisperModelSize.SMALL
WHISPER_COMPUTE_TYPE = "int8"

# Параметры фильтрации и VAD (Voice Activity Detection)
VAD_PARAMS = {
    "threshold": 0.65,
    "min_silence_duration_ms": 600
}
TEMPERATURE = 0.0
COMPRESSION_RATIO_THRESHOLD = 2.4
NO_SPEECH_THRESHOLD = 0.6

# Промпт для подмешивания терминов и командных фраз
TECHNICAL_PROMPT = (
    "Эни, any, стоп, stop, старт, start, очисти, заново, clear, reset, "
    "отформатируй код, выполни редирект, "
    "открой браузер, открой терминал, "
    "TypeScript, JavaScript, Python, C#, Dart, Rust, React, Expo, "
    "FastAPI, SQLAlchemy, PostgreSQL, Docker, VS Code, WebSocket, "
    "async, await, const, let, function, return, imports, exports."
)

# --- Режим и триггеры по умолчанию ---
DEFAULT_ENGINE_MODE = EngineVoiceMode.AUTO
DEFAULT_START_TRIGGERS = [
    "эни", "any", "компьютер", "слушай", "начать запись", "старт", "start", "джарвис"
]
DEFAULT_STOP_TRIGGERS = [
    "стоп", "stop", "готово", "конец сообщения", "хватит"
]
DEFAULT_SUBMIT_TRIGGERS = [
    "отправь", "отправить", "отправляй", "пошли", "отправить сообщение", "отправь сообщение",
    "submit", "send"
]
DEFAULT_CLEAR_TRIGGERS = [
    "очисти", "очистить", "заново", "стереть", "сброс", "сбрось", "отмена",
    "clear", "reset"
]

# --- Реестр голосовых команд (ID -> Данные + Синонимы) ---
DEFAULT_COMMAND_TRIGGERS = {
    # 1. Действия внутри VS Code
    "EXECUTE_REDIRECT": {
        "target": VoiceCommandTarget.VSCODE,
        "action": "extension.executeRedirect",
        "triggers": [
            "выполни редирект", "сделай редирект", "редирект"
        ],
    },
    "FORMAT_CODE": {
        "target": VoiceCommandTarget.VSCODE,
        "action": "editor.action.formatDocument",
        "triggers": [
            "отформатируй код",
            "отформатирую код",
            "форматируй код",
            "форматирование кода",
            "отформатировать код",
            "отформатируй",
            "отформатирую",
            "форматируй"
        ],
    },

    # 2. Действия для Desktop Agent (Управление ПК)
    "OPEN_BROWSER": {
        "target": VoiceCommandTarget.DESKTOP_AGENT,
        "action": "open_browser",
        "triggers": [
            "открой браузер", "запусти браузер", "браузер"
        ],
    },
    "OPEN_TERMINAL": {
        "target": VoiceCommandTarget.DESKTOP_AGENT,
        "action": "open_terminal",
        "triggers": [
            "запусти терминал", "открой терминал", "консоль", "терминал"
        ],
    },
}

# --- Функция получения путей CUDA для Windows ---
def setup_win32_cuda():
    if sys.platform == "win32":
        site_packages = os.path.join(sys.prefix, "Lib", "site-packages")
        cuda_paths = [
            os.path.join(site_packages, "nvidia", "cublas", "bin"),
            os.path.join(site_packages, "nvidia", "cudnn", "bin"),
            os.path.join(site_packages, "nvidia", "cuda_nvrtc", "bin"),
        ]
        for path in cuda_paths:
            if os.path.exists(path):
                os.add_dll_directory(path)
                os.environ["PATH"] = path + os.path.pathsep + os.environ.get("PATH", "")