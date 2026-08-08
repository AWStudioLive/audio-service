# main.py

import asyncio
import json
import logging
import re
import signal
import sys

import ctranslate2
import numpy as np
import sounddevice as sd
import websockets
from faster_whisper import WhisperModel

import config
from enums import EngineVoiceMode

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AudioService")

# Заглушаем внутренний спам библиотек faster_whisper и ctranslate2
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("ctranslate2").setLevel(logging.WARNING)

# Регистрируем пути к CUDA DLL
config.setup_win32_cuda()


def init_whisper_model() -> WhisperModel:
    """Инициализация модели Whisper с проверкой CUDA"""
    logger.info("--- Проверка аппаратного ускорения ---")
    try:
        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            logger.info(f"[GPU] Обнаружено CUDA-устройств: {cuda_count}")
            logger.info(
                f"[GPU] Загрузка Whisper ({config.WHISPER_MODEL_NAME.value}) на GPU..."
            )
            model = WhisperModel(
                config.WHISPER_MODEL_NAME,
                device="cuda",
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            logger.info("=== [УСПЕХ] Whisper работает на GPU (CUDA)! ===")
            return model
        else:
            logger.warning("[CPU] CUDA-устройства не обнаружены.")
    except (RuntimeError, ValueError) as e:
        logger.warning(
            f"[ВНИМАНИЕ] Не удалось запустить на CUDA ({e}). Переключаемся на CPU..."
        )

    logger.info(
        f"Загрузка модели Whisper ({config.WHISPER_MODEL_NAME.value}) на CPU..."
    )
    model = WhisperModel(
        config.WHISPER_MODEL_NAME,
        device="cpu",
        compute_type=config.WHISPER_COMPUTE_TYPE,
    )
    logger.info("=== [УСПЕХ] Whisper работает на CPU ===")
    return model


model = init_whisper_model()


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def match_trigger(raw_text: str, trigger_list: list) -> str | None:
    norm_text = normalize_text(raw_text)
    for trigger in trigger_list:
        norm_trigger = normalize_text(trigger)
        pattern = r"\b" + re.escape(norm_trigger) + r"\b"
        if re.search(pattern, norm_text) or norm_trigger in norm_text:
            return trigger
    return None


def match_command_trigger(
    raw_text: str, command_dict: dict
) -> tuple[str, str, dict] | None:
    """
    Ищет совпадение распознанного текста с массивом синонимов (triggers).
    Возвращает (command_id, matched_phrase, cmd_info)
    """
    norm_text = normalize_text(raw_text)

    for cmd_id, cmd_info in command_dict.items():
        triggers = cmd_info.get("triggers", [])
        for trigger_phrase in triggers:
            norm_trigger = normalize_text(trigger_phrase)
            pattern = r"\b" + re.escape(norm_trigger) + r"\b"
            if re.search(pattern, norm_text) or norm_trigger in norm_text:
                return cmd_id, trigger_phrase, cmd_info

    return None


def extract_text_before_trigger(raw_text: str, matched_trigger: str) -> str:
    parts = re.split(re.escape(matched_trigger), raw_text, flags=re.IGNORECASE)
    before = parts[0] if parts else ""
    return re.sub(r"[\s.,!?;\:]+$", "", before).strip()


def extract_text_after_trigger(raw_text: str, matched_trigger: str) -> str:
    parts = re.split(re.escape(matched_trigger), raw_text, flags=re.IGNORECASE)
    after = parts[1] if len(parts) > 1 else ""
    return re.sub(r"^[\s.,!?;\:]+", "", after).strip()


def _sync_transcribe(audio_float32: np.ndarray) -> str:
    """Синхронный вызов Whisper (выполняется в отдельном потоке)"""
    segments, _ = model.transcribe(
        audio_float32,
        language="ru",
        initial_prompt=config.TECHNICAL_PROMPT,
        condition_on_previous_text=False,
        temperature=config.TEMPERATURE,
        compression_ratio_threshold=config.COMPRESSION_RATIO_THRESHOLD,
        no_speech_threshold=config.NO_SPEECH_THRESHOLD,
        vad_filter=True,
        vad_parameters=config.VAD_PARAMS,
    )
    return " ".join([segment.text for segment in segments]).strip()


async def transcribe_chunk(audio_data: np.ndarray) -> str:
    """Асинхронная обёртка, предотвращающая блокировку event loop"""
    audio_float32 = audio_data.astype(np.float32)
    return await asyncio.to_thread(_sync_transcribe, audio_float32)


class VoiceSessionHandler:
    """Изолированный обработчик голосовой сессии одного клиентского подключения"""

    def __init__(self, websocket: websockets.WebSocketServerProtocol):
        self.websocket = websocket
        self.current_mode = config.DEFAULT_ENGINE_MODE
        self.triggers_start = list(config.DEFAULT_START_TRIGGERS)
        self.triggers_stop = list(config.DEFAULT_STOP_TRIGGERS)
        self.triggers_submit = list(config.DEFAULT_SUBMIT_TRIGGERS)
        self.triggers_clear = list(config.DEFAULT_CLEAR_TRIGGERS)
        self.triggers_commands = dict(config.DEFAULT_COMMAND_TRIGGERS)

        self.is_voice_session_active = False
        self.session_text_acc = []
        self.recording = []
        self.is_manual_recording = False
        self.is_muted = False
        self.stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"SoundDevice Status: {status}")
        if self.is_muted:
            return
        if (
            self.is_manual_recording
            or self.current_mode in (EngineVoiceMode.AUTO, EngineVoiceMode.COMMAND)
        ):
            self.recording.append(indata.copy())

    def start_stream(self):
        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    async def run(self):
        logger.info("[WebSocket] Расширение VS Code подключено.")
        self.start_stream()
        loop_task = asyncio.create_task(self._background_audio_loop())

        try:
            async for message in self.websocket:
                data = json.loads(message)
                logger.debug(f"Входящая команда: {data}")
                await self._handle_client_action(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info("[WebSocket] Соединение разорвано.")
        finally:
            loop_task.cancel()
            self.stop_stream()

    async def _background_audio_loop(self):
        while True:
            await asyncio.sleep(config.BACKGROUND_LOOP_INTERVAL)

            if self.is_muted:
                continue

            if (
                self.current_mode in (EngineVoiceMode.AUTO, EngineVoiceMode.COMMAND)
                and len(self.recording) > 0
            ):
                audio_chunks = self.recording.copy()
                self.recording = []

                audio_data = np.concatenate(audio_chunks, axis=0).flatten()

                min_samples = config.SAMPLE_RATE * config.MIN_AUDIO_DURATION_SEC
                if len(audio_data) < min_samples:
                    self.recording.extend(audio_chunks)
                    continue

                try:
                    text = await transcribe_chunk(audio_data)
                except (RuntimeError, ValueError) as e:
                    logger.error(f"Ошибка распознавания Whisper: {e}")
                    continue

                if not text:
                    continue

                # --- РЕЖИМ COMMAND (Только голосовые команды) ---
                if self.current_mode == EngineVoiceMode.COMMAND:
                    logger.info(f'[COMMAND] "{text}"')
                    matched_command = match_command_trigger(
                        text, self.triggers_commands
                    )

                    if matched_command:
                        cmd_id, trigger_phrase, cmd_info = matched_command
                        target_enum = cmd_info["target"]

                        logger.info(
                            f"[COMMAND MODE] Сработала фраза: '{trigger_phrase}' -> ID: {cmd_id} | Target: {target_enum.target_name}"
                        )

                        await self.websocket.send(
                            json.dumps({
                                "type": "VOICE_COMMAND_EXECUTE",
                                "command_id": cmd_id,
                                "phrase": trigger_phrase,
                                "payload": {
                                    "target": target_enum.to_dict(),
                                    "action": cmd_info["action"],
                                },
                            })
                        )
                    else:
                        logger.debug(f"[COMMAND MODE IGNORED] '{text}'")

                # --- РЕЖИМ AUTO (Диктовка + команды на паузе) ---
                elif self.current_mode == EngineVoiceMode.AUTO:
                    logger.info(
                        f'[AUTO] "{text}" | Активна: {self.is_voice_session_active}'
                    )

                    matched_submit = match_trigger(text, self.triggers_submit)
                    matched_start = match_trigger(text, self.triggers_start)
                    matched_stop = match_trigger(text, self.triggers_stop)
                    matched_clear = match_trigger(text, self.triggers_clear)
                    matched_command = match_command_trigger(
                        text, self.triggers_commands
                    )

                    await self._process_triggers(
                        text,
                        matched_submit,
                        matched_start,
                        matched_stop,
                        matched_clear,
                        matched_command,
                    )

    async def _process_triggers(
        self,
        text,
        matched_submit,
        matched_start,
        matched_stop,
        matched_clear,
        matched_command,
    ):
        if self.is_voice_session_active:
            # --- В РЕЖИМЕ ДИКТОВКИ (Внешние команды игнорируются) ---
            if matched_submit:
                before = extract_text_before_trigger(text, matched_submit)
                if before:
                    self.session_text_acc.append(before)

                full_text = " ".join(self.session_text_acc).strip()
                self.session_text_acc = []
                self.is_voice_session_active = False

                after = extract_text_after_trigger(text, matched_submit)
                if after:
                    self.session_text_acc.append(after)

                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_SUBMIT",
                        "text": full_text,
                    })
                )

            elif matched_stop:
                before = extract_text_before_trigger(text, matched_stop)
                if before:
                    self.session_text_acc.append(before)

                self.is_voice_session_active = False
                current_full = " ".join(self.session_text_acc).strip()

                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_ENDED",
                        "text": current_full,
                    })
                )

            else:
                self.session_text_acc.append(text.strip())
                current_full = " ".join(self.session_text_acc).strip()
                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_PARTIAL",
                        "text": current_full,
                    })
                )

        else:
            # --- В РЕЖИМЕ ПАУЗЫ (Обработка внешних команд) ---
            if matched_command:
                cmd_id, trigger_phrase, cmd_info = matched_command
                target_enum = cmd_info["target"]

                logger.info(
                    f"[КОМАНДА] Сработала фраза: '{trigger_phrase}' -> ID: {cmd_id} | Target: {target_enum.target_name}"
                )

                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_COMMAND_EXECUTE",
                        "command_id": cmd_id,
                        "phrase": trigger_phrase,
                        "payload": {
                            "target": target_enum.to_dict(),
                            "action": cmd_info["action"],
                        },
                    })
                )

            elif matched_submit:
                full_text = " ".join(self.session_text_acc).strip()
                self.session_text_acc = []
                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_SUBMIT",
                        "text": full_text,
                    })
                )

            elif matched_start:
                self.is_voice_session_active = True
                after = extract_text_after_trigger(text, matched_start)

                await self.websocket.send(
                    json.dumps({"type": "VOICE_SESSION_STARTED"})
                )

                if after:
                    self.session_text_acc.append(after)
                    current_full = " ".join(self.session_text_acc).strip()
                    await self.websocket.send(
                        json.dumps({
                            "type": "VOICE_SESSION_PARTIAL",
                            "text": current_full,
                        })
                    )

            elif matched_clear:
                self.session_text_acc = []
                logger.info("[ТРИГГЕР] Буфер сообщения очищен на паузе.")
                await self.websocket.send(
                    json.dumps({"type": "VOICE_SESSION_PARTIAL", "text": ""})
                )

            elif matched_stop:
                current_full = " ".join(self.session_text_acc).strip()
                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_ENDED",
                        "text": current_full,
                    })
                )

    async def _handle_client_action(self, data: dict):
        action = data.get("action")

        if action == "SET_MODE":
            requested_mode = data.get("mode", config.DEFAULT_ENGINE_MODE.value)
            try:
                self.current_mode = EngineVoiceMode(requested_mode)
            except ValueError:
                self.current_mode = config.DEFAULT_ENGINE_MODE

            custom_start = data.get("triggers_start")
            custom_stop = data.get("triggers_stop")
            custom_submit = data.get("triggers_submit")
            custom_clear = data.get("triggers_clear")

            self.triggers_start = (
                [t.lower() for t in custom_start]
                if isinstance(custom_start, list)
                else list(config.DEFAULT_START_TRIGGERS)
            )
            self.triggers_stop = (
                [t.lower() for t in custom_stop]
                if isinstance(custom_stop, list)
                else list(config.DEFAULT_STOP_TRIGGERS)
            )
            self.triggers_submit = (
                [t.lower() for t in custom_submit]
                if isinstance(custom_submit, list)
                else list(config.DEFAULT_SUBMIT_TRIGGERS)
            )
            self.triggers_clear = (
                [t.lower() for t in custom_clear]
                if isinstance(custom_clear, list)
                else list(config.DEFAULT_CLEAR_TRIGGERS)
            )

            self.is_voice_session_active = False
            self.is_muted = False
            self.session_text_acc = []
            self.recording = []
            logger.info(
                f"Настройки обновлены (Режим: {self.current_mode.value})"
            )

        elif action == "START":
            self.is_muted = False
            self.recording = []
            if self.current_mode == EngineVoiceMode.MANUAL:
                self.is_manual_recording = True
            else:
                self.is_voice_session_active = True
                await self.websocket.send(
                    json.dumps({"type": "VOICE_SESSION_STARTED"})
                )
            logger.info("Запись/Сессия активирована.")

        elif action == "STOP":
            self.is_manual_recording = False

            if self.current_mode == EngineVoiceMode.MANUAL:
                self.is_muted = True
                recording_to_process = self.recording.copy()
                self.recording = []
                logger.info("Замьючено / Остановлено (MANUAL).")

                if recording_to_process:
                    audio_data = np.concatenate(
                        recording_to_process, axis=0
                    ).flatten()
                    text = await transcribe_chunk(audio_data)
                    logger.info(f"MANUAL_RESULT -> '{text}'")
                    await self.websocket.send(
                        json.dumps({"type": "MANUAL_RESULT", "text": text})
                    )
            else:
                self.is_voice_session_active = False
                self.is_muted = False
                current_full = " ".join(self.session_text_acc).strip()
                self.recording = []
                logger.info("Сессия приостановлена. Буфер сохранен.")
                await self.websocket.send(
                    json.dumps({
                        "type": "VOICE_SESSION_ENDED",
                        "text": current_full,
                    })
                )


async def audio_handler(websocket: websockets.WebSocketServerProtocol):
    session = VoiceSessionHandler(websocket)
    await session.run()


async def main():
    stop_event = asyncio.Event()

    def shutdown_signal_handler(sig, frame):
        logger.info("Получен сигнал завершения. Остановка микросервиса...")
        stop_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    else:
        signal.signal(signal.SIGINT, shutdown_signal_handler)
        signal.signal(signal.SIGTERM, shutdown_signal_handler)

    async with websockets.serve(
        audio_handler,
        config.WS_HOST,
        config.WS_PORT,
        ping_interval=config.WS_PING_INTERVAL,
        ping_timeout=config.WS_PING_TIMEOUT,
    ):
        logger.info(
            f"Микросервис запущен на ws://{config.WS_HOST}:{config.WS_PORT}"
        )
        await stop_event.wait()

    logger.info("Микросервис успешно остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass