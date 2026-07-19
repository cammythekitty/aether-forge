"""
Æther Forge — Voice
Whisper detection, audio recording, push-to-talk.
"""

import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from config import OS, PTT_KEY, RECORD_SECS, SAMPLE_RATE, WHISPER_MODEL_PATHS, WHISPER_PREFERRED
from ui.terminal import forge_print, C

WHISPER_BIN   = None
WHISPER_MODEL = None
_VOICE_CANCEL_EVENT = threading.Event()

# ─── Detection ────────────────────────────────────────────────────────────────

def find_whisper():
    global WHISPER_BIN, WHISPER_MODEL

    for name in ["whisper-cli", "whisper.cpp", "whisper"]:
        cmd = ["where", name] if OS == "Windows" else ["which", name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            WHISPER_BIN = result.stdout.strip()
            break

    for mp in WHISPER_MODEL_PATHS:
        if mp.exists():
            for pref in WHISPER_PREFERRED:
                candidate = mp / pref
                if candidate.exists():
                    WHISPER_MODEL = str(candidate)
                    return
            models = list(mp.glob("*.bin"))
            if models:
                WHISPER_MODEL = str(models[0])
                return

def is_ready() -> bool:
    return bool(WHISPER_BIN and WHISPER_MODEL)

# ─── Recording ────────────────────────────────────────────────────────────────

def reset_voice_cancel() -> None:
    _VOICE_CANCEL_EVENT.clear()


def cancel_voice_recording() -> None:
    _VOICE_CANCEL_EVENT.set()


def record_audio(stop_event: threading.Event | None = None, duration: float | None = None) -> str | None:
    stop_event = stop_event if stop_event is not None else _VOICE_CANCEL_EVENT
    duration = duration if duration is not None else RECORD_SECS

    if stop_event.is_set():
        return None

    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io.wavfile import write as wav_write

        forge_print("⟁ Listening...", C.EMBER)
        audio_chunks = []

        def callback(indata, frames, time_info, status):
            audio_chunks.append(indata.copy())

        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback)
        stream.start()
        start = time.monotonic()
        while not stop_event.is_set() and (time.monotonic() - start) < duration:
            sd.sleep(50)
        stream.stop()
        stream.close()

        if not audio_chunks:
            return None

        audio = np.concatenate(audio_chunks, axis=0).astype(np.int16)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_write(tmp.name, SAMPLE_RATE, audio)
        return tmp.name
    except Exception as e:
        forge_print(f"⟁ Audio error: {e}", C.EMBER)
        return None

def transcribe(wav_path: str) -> str | None:
    if not is_ready():
        return None
    try:
        result = subprocess.run(
            [WHISPER_BIN, "-m", WHISPER_MODEL, "-f", wav_path, "--no-timestamps", "-nt"],
            capture_output=True, text=True, timeout=30
        )
        os.unlink(wav_path)
        transcript = result.stdout.strip()
        if transcript:
            forge_print(f"⟁ Heard: {transcript}", C.DIM)
        return transcript or None
    except Exception as e:
        forge_print(f"⟁ Transcription error: {e}", C.EMBER)
        return None

# ─── Push to talk ─────────────────────────────────────────────────────────────

def get_voice_input(stop_event: threading.Event | None = None) -> str | None:
    stop_event = stop_event if stop_event is not None else _VOICE_CANCEL_EVENT

    try:
        from pynput import keyboard

        forge_print(f"⟁ Hold [{PTT_KEY}] to speak...", C.DIM)
        recording = threading.Event()
        done      = threading.Event()
        wav_path  = [None]

        def on_press(key):
            try:
                if hasattr(key, "char") and key.char == PTT_KEY:
                    if not recording.is_set():
                        recording.set()
            except Exception:
                pass

        def on_release(key):
            try:
                if hasattr(key, "char") and key.char == PTT_KEY:
                    done.set()
                    return False
            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        recording.wait(timeout=30)
        wav_path[0] = record_audio(stop_event=stop_event)
        done.wait(timeout=10)
        listener.stop()

        if stop_event.is_set() or not wav_path[0]:
            return None
        return transcribe(wav_path[0])
    except Exception as e:
        forge_print(f"⟁ PTT error: {e}", C.EMBER)
        return None