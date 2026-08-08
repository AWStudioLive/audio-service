# 🎙️ Микросервис голосового движка Whisper

<p align="center">
  <a href="../README.md">English</a> | <b>Русский</b>
</p>

---

Высокопроизводительный асинхронный микросервис для распознавания речи и маршрутизации голосовых команд в реальном времени с использованием **faster-whisper** (CTranslate2) и **WebSockets**. Предназначен для интеграции голосового ввода и автоматизированного выполнения команд в расширения VS Code и системные Desktop-агенты.

## 🚀 Возможности

- **Аппаратное ускорение:** Автоматическое определение CUDA GPU (NVIDIA) с фоллбэком на CPU.
- **Автонастройка CUDA под Windows:** Автоматическое добавление путей к DLL-библиотекам CUDA из pip-пакетов.
- **Гибкие режимы обработки:** Поддержка режимов `MANUAL` (Push-to-Talk), `AUTO` (Диктовка) и `COMMAND` (Выполнение команд).
- **Маршрутизация голосовых команд:** Сопоставление сказанных фраз с реестром команд и отправка событий `VOICE_COMMAND_EXECUTE` для VS Code или внешних Desktop-агентов через HTTP/REST.
- **Распознавание триггеров:** Настраиваемые фразы активации, отправки, очистки и остановки с нормализацией регулярными выражениями.
- **Протокол WebSocket:** Асинхронное взаимодействие на основе JSON-событий.
- **Контекстный словарь:** Подмешивание терминов через `TECHNICAL_PROMPT` для повышения точности распознавания синтаксиса кода и командных фраз.

## 📁 Структура проекта

```text
.
├── main.py          # WebSocket-сервер, цикл обработки аудио и движок распознавания Whisper
├── config.py        # Конфигурация сервиса, параметры, триггеры и реестр команд
├── enums.py         # Enum для моделей Whisper, режимов работы и целей команд
├── requirements.txt # Зависимости Python
├── pyproject.toml   # Метаданные проекта и зависимости
├── README.md        # Документация (English)
└── docs/
    └── README.ru.md # Документация (Русский)
```

## 📋 Требования

- **Python:** `>= 3.12, < 3.13`
- **NVIDIA GPU:** Рекомендуется для ускорения CUDA (серия GTX 1050 или новее)
- **Захват аудио:** Рабочий микрофон, выбранный по умолчанию в системе

## 🛠️ Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone [https://github.com/AWStudioLive/audio-service.git](https://github.com/AWStudioLive/audio-service.git)
   cd audio-service
   ```

2. **Создайте и активируйте виртуальное окружение:**
   ```bash
   python -m venv .venv

   # Windows:
   .venv\Scripts\activate

   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

## 🚦 Запуск

Запустите WebSocket-сервер:

```bash
python main.py
```

Сервер начнет принимать соединения по адресу `ws://localhost:8765`.

## 🔄 Режимы работы

1. **`manual` (Ручной / Push-to-Talk):** Запись запускается по действию `START` и распознается полностью после команды `STOP`.
2. **`auto` (Автоматический / По умолчанию):** Интерактивная диктовка с распознаванием команд во время пауз. Открывает сессию по триггеру старта (`VOICE_SESSION_STARTED`), транслирует промежуточный текст (`VOICE_SESSION_PARTIAL`), отправляет собранный текст по триггеру отправки (`VOICE_SESSION_SUBMIT`) и закрывает сессию по триггеру стопа (`VOICE_SESSION_ENDED`).
3. **`command` (Командный):** Режим строгого выполнения команд. Отключает накопление текста для чата/редактора и сопоставляет входящий звук исключительно с `DEFAULT_COMMAND_TRIGGERS`.

## ⚙️ Система голосовых команд

Команды задаются в `config.py` в словаре `DEFAULT_COMMAND_TRIGGERS` и связываются с целями из `enums.py` (`VoiceCommandTarget`):

* **`vscode`**: Команды расширения VS Code (например, `editor.action.formatDocument`, `extension.executeRedirect`).
* **`desktop_agent`**: Внешний агент управления ОС через HTTP-эндпоинты (например, открытие браузера или терминала).

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

## 📡 Спецификация WebSocket API

### Входящие команды (Клиент -> Сервер)

- **Установка режима и триггеров:**
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
- **Запуск записи / размьючивание:**
  ```json
  { "action": "START" }
  ```
- **Остановка записи / мьют:**
  ```json
  { "action": "STOP" }
  ```

### Исходящие события (Сервер -> Клиент)

- **`MANUAL_RESULT`**: Результат распознавания после команды `STOP` в режиме `manual`.
- **`VOICE_SESSION_STARTED`**: Старт сессии в режиме `auto`.
- **`VOICE_SESSION_PARTIAL`**: Обновления надиктованного текста в реальном времени.
- **`VOICE_SESSION_SUBMIT`**: Отправка накопившегося текста без закрытия сессии.
- **`VOICE_SESSION_ENDED`**: Завершение сессии по триггеру остановки.
- **`VOICE_COMMAND_EXECUTE`**: Событие, отправляемое при совпадении сказанной фразы с командой:
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

## 📄 Лицензия

MIT