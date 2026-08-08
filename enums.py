# enums.py

from enum import Enum


class WhisperModelSize(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v3"


class EngineVoiceMode(str, Enum):
    MANUAL = "manual"    # Push-to-Talk (чистый ввод по кнопке)
    COMMAND = "command"  # Строго голосовые команды (без накопления текста)
    AUTO = "auto"        # Умная сессия диктовки + команды на паузе


class VoiceCommandTarget(Enum):
    """
    Enum целей голосовых команд.
    Хранит служебное имя, адрес (URL/Endpoint) и HTTP-метод.
    """
    # 1. Расширение редактора кода
    VSCODE = ("vscode", "vscode://command", "EXECUTE")

    # 2. Агент управления ОС и рабочим столом (открыть браузер, приложения)
    DESKTOP_AGENT = ("desktop_agent", "http://localhost:9001/api/v1", "POST")

    def __init__(self, target_name: str, address: str, method: str):
        self.target_name = target_name
        self.address = address
        self.method = method

    def to_dict(self) -> dict:
        """Сериализация свойств Enum в словарь для отправки по WebSocket"""
        return {
            "name": self.target_name,
            "address": self.address,
            "method": self.method,
        }