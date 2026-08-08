# config.py

import os
import sys

# Импортируем типы из enums
from enums import WhisperModelSize

# --- Настройки сервера ---
WS_HOST = "localhost"
WS_PORT = 8765

# --- Параметры аудио ---
SAMPLE_RATE = 16000
CHANNELS = 1

# --- Настройки Whisper ---
WHISPER_MODEL_NAME = WhisperModelSize.SMALL
WHISPER_COMPUTE_TYPE = "int8"

# Параметры фильтрации и VAD (Voice Activity Detection)
VAD_PARAMS = {
    "threshold": 0.5,
    "min_silence_duration_ms": 500
}
TEMPERATURE = 0.0
COMPRESSION_RATIO_THRESHOLD = 2.4
NO_SPEECH_THRESHOLD = 0.6

# Промпт для подмешивания терминов
TECHNICAL_PROMPT = (
    "Эни, TypeScript, JavaScript, Python, C#, Dart, Rust, React, Expo, "
    "FastAPI, SQLAlchemy, PostgreSQL, Docker, VS Code, WebSocket, "
    "async, await, const, let, function, return, imports, exports."
)

# --- Триггеры по умолчанию ---
DEFAULT_START_TRIGGERS = ["эни", "компьютер", "слушай", "начать запись", "старт", "джарвис"]
DEFAULT_STOP_TRIGGERS = ["стоп", "готово", "конец сообщения", "хватит"]
DEFAULT_SUBMIT_TRIGGERS = ["отправь", "отправить", "отправляй", "пошли", "отправить сообщение", "отправь сообщение"]

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