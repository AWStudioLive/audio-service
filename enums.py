# enums.py

from enum import Enum


class WhisperModelSize(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v3"


class EngineVoiceMode(str, Enum):
    MANUAL = "manual"
    CONTINUOUS = "continuous"
    BOUNDED = "bounded"