# main.py

import asyncio
import json
import re

import ctranslate2
import numpy as np
import sounddevice as sd
import websockets
from faster_whisper import WhisperModel

import config
from enums import EngineVoiceMode

# Регистрируем пути к CUDA DLL
config.setup_win32_cuda()


def init_whisper_model():
    """Инициализация модели Whisper"""
    print("--- Проверка аппаратного ускорения ---")
    try:
        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            print(f"[GPU] Обнаружено CUDA-устройств: {cuda_count}")
            print(
                f"[GPU] Загрузка Whisper ({config.WHISPER_MODEL_NAME.value}) на GPU..."
            )
            model = WhisperModel(
                config.WHISPER_MODEL_NAME,
                device="cuda",
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            print("=== [УСПЕХ] Whisper работает на GPU (CUDA)! ===")
            return model
        else:
            print("[CPU] CUDA-устройства не обнаружены.")
    except (RuntimeError, ValueError) as e:
        print(
            f"[ВНИМАНИЕ] Не удалось запустить на CUDA ({e}). Переключаемся на CPU..."
        )

    print(
        f"Загрузка модели Whisper ({config.WHISPER_MODEL_NAME.value}) на CPU..."
    )
    model = WhisperModel(
        config.WHISPER_MODEL_NAME,
        device="cpu",
        compute_type=config.WHISPER_COMPUTE_TYPE,
    )
    print("=== [УСПЕХ] Whisper работает на CPU ===")
    return model


model = init_whisper_model()


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def match_trigger(raw_text: str, trigger_list: list):
    norm_text = normalize_text(raw_text)
    for trigger in trigger_list:
        norm_trigger = normalize_text(trigger)
        pattern = r"\b" + re.escape(norm_trigger) + r"\b"
        if re.search(pattern, norm_text) or norm_trigger in norm_text:
            return trigger
    return None


def extract_text_before_trigger(raw_text: str, matched_trigger: str) -> str:
    parts = re.split(re.escape(matched_trigger), raw_text, flags=re.IGNORECASE)
    before = parts[0] if parts else ""
    return re.sub(r"[\s.,!?;\:]+$", "", before).strip()


def extract_text_after_trigger(raw_text: str, matched_trigger: str) -> str:
    parts = re.split(re.escape(matched_trigger), raw_text, flags=re.IGNORECASE)
    after = parts[1] if len(parts) > 1 else ""
    return re.sub(r"^[\s.,!?;\:]+", "", after).strip()


async def transcribe_chunk(audio_data):
    audio_float32 = audio_data.astype(np.float32)
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


async def audio_handler(websocket):
    print("\n[WebSocket] Расширение VS Code успешно подключено.")

    current_mode = config.DEFAULT_ENGINE_MODE
    triggers_start = list(config.DEFAULT_START_TRIGGERS)
    triggers_stop = list(config.DEFAULT_STOP_TRIGGERS)
    triggers_submit = list(config.DEFAULT_SUBMIT_TRIGGERS)

    is_voice_session_active = False
    session_text_acc = []

    recording = []
    is_manual_recording = False
    is_muted = False

    def callback(indata, frames, time, status):
        nonlocal is_manual_recording, current_mode, is_muted
        if is_muted:
            return
        if is_manual_recording or current_mode == EngineVoiceMode.AUTO:
            recording.append(indata.copy())

    stream = sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        callback=callback,
    )
    stream.start()

    async def background_audio_loop():
        nonlocal recording, is_voice_session_active, session_text_acc, current_mode
        nonlocal triggers_start, triggers_stop, triggers_submit, is_muted

        while True:
            await asyncio.sleep(2.0)

            if is_muted:
                continue

            if current_mode == EngineVoiceMode.AUTO and len(recording) > 0:
                audio_chunks = recording.copy()
                recording = []

                audio_data = np.concatenate(audio_chunks, axis=0).flatten()
                text = await transcribe_chunk(audio_data)

                if not text:
                    continue

                print(
                    f'\n[AUTO РАСПОЗНАНО] "{text}" (Сессия активна: {is_voice_session_active})'
                )

                matched_submit = match_trigger(text, triggers_submit)
                matched_start = match_trigger(text, triggers_start)
                matched_stop = match_trigger(text, triggers_stop)

                if is_voice_session_active:
                    if matched_submit:
                        before_submit = extract_text_before_trigger(
                            text, matched_submit
                        )
                        if before_submit:
                            session_text_acc.append(before_submit)

                        full_result_text = " ".join(session_text_acc).strip()
                        is_voice_session_active = True
                        session_text_acc = []

                        after_submit = extract_text_after_trigger(
                            text, matched_submit
                        )
                        if after_submit:
                            session_text_acc.append(after_submit)

                        await websocket.send(
                            json.dumps({
                                "type": "VOICE_SESSION_SUBMIT",
                                "text": full_result_text,
                            })
                        )

                    elif matched_stop:
                        before_stop = extract_text_before_trigger(
                            text, matched_stop
                        )
                        if before_stop:
                            session_text_acc.append(before_stop)

                        full_result_text = " ".join(session_text_acc).strip()
                        is_voice_session_active = False
                        session_text_acc = []

                        await websocket.send(
                            json.dumps({
                                "type": "VOICE_SESSION_ENDED",
                                "text": full_result_text,
                            })
                        )

                    else:
                        session_text_acc.append(text.strip())
                        current_full = " ".join(session_text_acc).strip()
                        await websocket.send(
                            json.dumps({
                                "type": "VOICE_SESSION_PARTIAL",
                                "text": current_full,
                            })
                        )

                else:
                    if matched_submit:
                        await websocket.send(
                            json.dumps({
                                "type": "VOICE_SESSION_SUBMIT",
                                "text": "",
                            })
                        )

                    elif matched_start:
                        is_voice_session_active = True
                        session_text_acc = []
                        after_start = extract_text_after_trigger(
                            text, matched_start
                        )

                        await websocket.send(
                            json.dumps({"type": "VOICE_SESSION_STARTED"})
                        )

                        if after_start:
                            session_text_acc.append(after_start)
                            current_full = " ".join(session_text_acc).strip()
                            await websocket.send(
                                json.dumps({
                                    "type": "VOICE_SESSION_PARTIAL",
                                    "text": current_full,
                                })
                            )

    loop_task = asyncio.create_task(background_audio_loop())

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            print(f"\n[WS RECV] Входящая команда от VS Code: {data}")

            if action == "SET_MODE":
                requested_mode = data.get(
                    "mode", config.DEFAULT_ENGINE_MODE.value
                )
                try:
                    current_mode = EngineVoiceMode(requested_mode)
                except ValueError:
                    current_mode = config.DEFAULT_ENGINE_MODE

                custom_start = data.get("triggers_start")
                custom_stop = data.get("triggers_stop")
                custom_submit = data.get("triggers_submit")

                triggers_start = (
                    [t.lower() for t in custom_start]
                    if isinstance(custom_start, list)
                    else list(config.DEFAULT_START_TRIGGERS)
                )
                triggers_stop = (
                    [t.lower() for t in custom_stop]
                    if isinstance(custom_stop, list)
                    else list(config.DEFAULT_STOP_TRIGGERS)
                )
                triggers_submit = (
                    [t.lower() for t in custom_submit]
                    if isinstance(custom_submit, list)
                    else list(config.DEFAULT_SUBMIT_TRIGGERS)
                )

                is_voice_session_active = False
                is_muted = False
                session_text_acc = []
                recording = []
                print("[СТАТУС] Настройки обновлены:")
                print(f"  ├─ Режим (current_mode): {current_mode.value}")
                print(f"  ├─ Триггеры старта: {triggers_start}")
                print(f"  ├─ Триггеры стопа: {triggers_stop}")
                print(f"  └─ Триггеры отправки: {triggers_submit}")

            elif action == "START":
                is_muted = False
                recording = []
                if current_mode == EngineVoiceMode.MANUAL:
                    is_manual_recording = True
                print("[Status] Размьючено / Запись включена.")

            elif action == "STOP":
                is_manual_recording = False
                is_voice_session_active = False
                is_muted = True
                recording_to_process = recording.copy()
                recording = []
                print("[Status] Замьючено / Остановлено.")

                if (
                    current_mode == EngineVoiceMode.MANUAL
                    and recording_to_process
                ):
                    audio_data = np.concatenate(
                        recording_to_process, axis=0
                    ).flatten()
                    text = await transcribe_chunk(audio_data)
                    print(f"  └─► [WS SEND] MANUAL_RESULT -> '{text}'")
                    await websocket.send(
                        json.dumps({"type": "MANUAL_RESULT", "text": text})
                    )

    except websockets.exceptions.ConnectionClosed:
        print("\n[WebSocket] Соединение разорвано.")
    finally:
        loop_task.cancel()
        stream.stop()
        stream.close()


async def main():
    async with websockets.serve(
        audio_handler, config.WS_HOST, config.WS_PORT
    ):
        print(
            f"\nМикросервис запущен и готов к работе на ws://{config.WS_HOST}:{config.WS_PORT}"
        )
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())