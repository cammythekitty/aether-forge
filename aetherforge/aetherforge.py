#!/usr/bin/env python3
"""
Æther Forge — Powered by Vaelora Systems
A fully local AI environment that grows with you.
"""

import os
import sys
import platform
import subprocess
import threading
import tempfile
import json
import time
import importlib.util
import signal
import atexit
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

LLAMA_SERVER_URL = "http://localhost:8080"
LLAMA_PORT       = 8080
MODEL_CTX        = 2048
TOOLS_DIR        = Path.home() / ".aetherforge" / "tools"
FORGE_DIR        = Path.home() / ".aetherforge"

WHISPER_BIN      = None
WHISPER_MODEL    = None
LLAMA_PROC       = None

OS    = platform.system()
DE    = os.environ.get("XDG_SESSION_TYPE", "").lower()
SHELL = "powershell" if OS == "Windows" else "bash"
PTT_KEY = "`"

MODEL_SEARCH_DIRS = [
    Path.home() / "Documents" / "Ai_Models",
    Path.home() / "Documents" / "AI_Models",
    Path.home() / "Models",
    Path.home() / "models",
    Path.home() / ".local" / "share" / "models",
    Path.home() / "Downloads",
]

# ─── Colours ──────────────────────────────────────────────────────────────────

class C:
    AMBER  = "\033[38;2;255;140;0m"
    EMBER  = "\033[38;2;255;69;0m"
    DIM    = "\033[38;2;100;100;100m"
    WHITE  = "\033[38;2;224;224;224m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

def forge_print(msg, colour=C.AMBER, **kwargs):
    print(f"{colour}{msg}{C.RESET}", **kwargs)

def dim_print(msg):
    print(f"{C.DIM}{msg}{C.RESET}")

# ─── Boot animation ───────────────────────────────────────────────────────────

RUNES = ["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚷ", "ᚹ", "ᛁ", "ᛃ", "ᛇ", "ᛚ", "ᛟ"]

def boot_animation():
    os.system("clear" if OS != "Windows" else "cls")

    for i in range(len(RUNES)):
        os.system("clear" if OS != "Windows" else "cls")
        lit = [
            f"{C.AMBER}{C.BOLD}{r}{C.RESET}" if j <= i else f"{C.DIM}{r}{C.RESET}"
            for j, r in enumerate(RUNES)
        ]
        print("\n\n")
        print("        " + "  ".join(lit[:6]))
        print("        " + "  ".join(lit[6:]))
        time.sleep(0.12)

    time.sleep(0.4)

    for i in range(len(RUNES)):
        os.system("clear" if OS != "Windows" else "cls")
        lit = [
            f"{C.DIM}{r}{C.RESET}" if j <= i else f"{C.AMBER}{C.BOLD}{r}{C.RESET}"
            for j, r in enumerate(RUNES)
        ]
        print("\n\n")
        print("        " + "  ".join(lit[:6]))
        print("        " + "  ".join(lit[6:]))
        time.sleep(0.06)

    os.system("clear" if OS != "Windows" else "cls")
    corner = f"{C.DIM}{'  '.join(RUNES[:6])}{C.RESET}"
    print(f"  {corner}\n")
    print(f"{C.AMBER}{C.BOLD}        Æ T H E R  F O R G E{C.RESET}")
    print(f"{C.DIM}        A fully local AI environment that grows with you.{C.RESET}")
    print(f"{C.DIM}        Powered by Vaelora Systems{C.RESET}")
    print()

# ─── Model detection ──────────────────────────────────────────────────────────

def find_model() -> str | None:
    for d in MODEL_SEARCH_DIRS:
        if d.exists():
            candidates = sorted(d.glob("*.gguf"), reverse=True)
            for f in candidates:
                if "qwen" in f.name.lower():
                    return str(f)
    return None

# ─── llama-server lifecycle ───────────────────────────────────────────────────

def find_llama_server() -> str | None:
    candidates = ["llama-server", "llama_server"]
    for c in candidates:
        cmd = ["where", c] if OS == "Windows" else ["which", c]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    return None

def server_healthy() -> bool:
    try:
        import requests
        resp = requests.get(f"{LLAMA_SERVER_URL}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False

def start_llama_server(model_path: str) -> bool:
    global LLAMA_PROC

    if server_healthy():
        forge_print("⟁ llama-server already running.", C.DIM)
        return True

    binary = find_llama_server()
    if not binary:
        forge_print("⟁ llama-server not found in PATH.", C.EMBER)
        return False

    forge_print("⟁ Starting llama-server...", C.DIM)
    dim_print(f"  Model: {Path(model_path).name}")

    log_file = open(FORGE_DIR / "llama-server.log", "w")

    LLAMA_PROC = subprocess.Popen(
        [binary, "-m", model_path, "--port", str(LLAMA_PORT), "-c", str(MODEL_CTX)],
        stdout=log_file,
        stderr=log_file,
        start_new_session=True
    )

    forge_print("⟁ Waiting for model to load", C.DIM, end="", flush=True)
    for _ in range(60):
        if server_healthy():
            print(f" {C.AMBER}ready.{C.RESET}")
            return True
        print(f"{C.DIM}.{C.RESET}", end="", flush=True)
        time.sleep(1)

    print()
    forge_print("⟁ llama-server failed to start. Check ~/.aetherforge/llama-server.log", C.EMBER)
    return False

def stop_llama_server():
    global LLAMA_PROC
    if LLAMA_PROC and LLAMA_PROC.poll() is None:
        forge_print("\n⟁ Shutting down llama-server...", C.DIM)
        LLAMA_PROC.terminate()
        try:
            LLAMA_PROC.wait(timeout=5)
        except subprocess.TimeoutExpired:
            LLAMA_PROC.kill()

# ─── Setup ────────────────────────────────────────────────────────────────────

def setup_dirs():
    FORGE_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    git_dir = TOOLS_DIR / ".git"
    if not git_dir.exists():
        subprocess.run(["git", "init", str(TOOLS_DIR)], capture_output=True)
        readme = TOOLS_DIR / "README.md"
        readme.write_text("# Æther Forge — Tools\nThis directory is owned by Æther Forge. Tools are written and committed automatically.\n")
        subprocess.run(["git", "-C", str(TOOLS_DIR), "add", "."], capture_output=True)
        subprocess.run(["git", "-C", str(TOOLS_DIR), "commit", "-m", "Initial forge — Æther Forge awakens"], capture_output=True)
        forge_print("⟁ Tools directory initialised.")

# ─── Whisper ──────────────────────────────────────────────────────────────────

def find_whisper():
    global WHISPER_BIN, WHISPER_MODEL

    candidates = ["whisper-cli", "whisper.cpp", "whisper"]
    for c in candidates:
        result = subprocess.run(
            ["where", c] if OS == "Windows" else ["which", c],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            WHISPER_BIN = result.stdout.strip()
            break

    model_paths = [
        Path.home() / ".local" / "share" / "whisper.cpp" / "models",
        Path("/usr/share/whisper.cpp/models"),
        Path("/usr/share/whisper-cpp/models"),
        FORGE_DIR / "models",
    ]
    preferred = ["ggml-base.en.bin", "ggml-small.en.bin", "ggml-tiny.en.bin"]

    for mp in model_paths:
        if mp.exists():
            for pref in preferred:
                candidate = mp / pref
                if candidate.exists():
                    WHISPER_MODEL = str(candidate)
                    return
            models = list(mp.glob("*.bin"))
            if models:
                WHISPER_MODEL = str(models[0])
                return

# ─── Voice input ──────────────────────────────────────────────────────────────

def record_audio(duration=6) -> str | None:
    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io.wavfile import write as wav_write

        forge_print("⟁ Listening...", C.EMBER)
        sample_rate = 16000
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                       channels=1, dtype="int16")
        sd.wait()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_write(tmp.name, sample_rate, audio)
        return tmp.name
    except Exception as e:
        forge_print(f"⟁ Audio error: {e}", C.EMBER)
        return None

def transcribe(wav_path: str) -> str | None:
    if not WHISPER_BIN or not WHISPER_MODEL:
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

def get_voice_input() -> str | None:
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
        wav_path[0] = record_audio(duration=6)
        done.wait(timeout=10)
        listener.stop()

        if wav_path[0]:
            return transcribe(wav_path[0])
        return None
    except Exception as e:
        forge_print(f"⟁ PTT error: {e}", C.EMBER)
        return None

# ─── Brain ────────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    tools = list_tools()
    tools_str = "\n".join(f"  - {t}" for t in tools) if tools else "  (none yet)"

    return f"""You are Æther Forge, a fully local AI assistant with complete control over the user's computer.

ENVIRONMENT:
  OS: {OS}
  Shell: {SHELL}
  Display: {DE or 'tty'}
  Wayland: {'yes' if DE == 'wayland' else 'no'}
  Tools dir: {TOOLS_DIR}
  Terminal emulator: foot
  Vesktop (Discord) flatpak command: dev.vencord.Vesktop

AVAILABLE TOOLS (pre-written Python modules you can call):
{tools_str}

YOUR JOB:
  The user gives you a command. You execute it. No explanation. Just code.
  Respond with raw Python only. No markdown. No backticks. No explanation.

EXECUTION ENVIRONMENT (already available, use directly):
  os, sys, subprocess, Path, time, json, requests
  run(cmd: str) -> str        — runs a shell command, returns + prints output
  run_tool(name: str)         — loads and runs a saved tool by name
  git_commit(message: str)    — stages and commits everything in tools dir
  TOOLS_DIR                   — Path to tools directory
  FORGE_DIR                   — Path to ~/.aetherforge

RUNNING TOOLS:
  To run a saved tool ALWAYS use: run_tool("toolname")
  Never use run() with a Path object. Never call tools as shell scripts.

SELF UPGRADE:
  If a task was complex or repetitive, save it as a reusable tool:
  1. Write the tool source as a plain Python string
  2. Save: open(TOOLS_DIR / 'toolname.py', 'w').write("source string here")
  3. Call: git_commit("Added toolname: what it does")
  Never write __code__.co_code — always write plain source code as a string.

PLATFORM:
  {'Use ydotool for simulating keypresses on Wayland.' if DE == 'wayland' else ''}
  {'Use xdotool for keypresses on X11.' if DE == 'x11' else ''}
  Always use start_new_session=True in subprocess.Popen when launching GUI apps.
  Use bash syntax for shell commands.

OUTPUT:
  Only executable Python. Nothing else.
"""

def ask_qwen(user_input: str) -> str | None:
    try:
        import requests

        payload = {
            "model": "qwen",
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user",   "content": user_input}
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "stream": False
        }

        forge_print("⟁ Forging...", C.DIM)
        resp = requests.post(
            f"{LLAMA_SERVER_URL}/v1/chat/completions",
            json=payload, timeout=120
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        forge_print(f"⟁ Brain error: {e}", C.EMBER)
        return None

# ─── Tools ────────────────────────────────────────────────────────────────────

def list_tools() -> list[str]:
    if not TOOLS_DIR.exists():
        return []
    return [f.stem for f in TOOLS_DIR.glob("*.py")]

def load_tools(env: dict):
    for tool_file in TOOLS_DIR.glob("*.py"):
        try:
            spec   = importlib.util.spec_from_file_location(tool_file.stem, tool_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            env[tool_file.stem] = module
        except Exception as e:
            dim_print(f"  Could not load tool {tool_file.stem}: {e}")

# ─── Executor ─────────────────────────────────────────────────────────────────

def make_env() -> dict:
    import requests

    def run(cmd: str) -> str:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out = (result.stdout + result.stderr).strip()
        if out:
            print(out)
        return out

    def git_commit(message: str):
        subprocess.run(["git", "-C", str(TOOLS_DIR), "add", "."], capture_output=True)
        subprocess.run(["git", "-C", str(TOOLS_DIR), "commit", "-m", message], capture_output=True)
        forge_print(f"⟁ Committed: {message}", C.DIM)

    def run_tool(name: str):
        tool_file = TOOLS_DIR / f"{name}.py"
        if not tool_file.exists():
            forge_print(f"⟁ Tool not found: {name}", C.EMBER)
            return
        spec   = importlib.util.spec_from_file_location(name, tool_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, name, None)
        if fn:
            fn()
        else:
            forge_print(f"⟁ No callable '{name}' in tool.", C.EMBER)

    env = {
        "os":         os,
        "sys":        sys,
        "subprocess": subprocess,
        "Path":       Path,
        "time":       time,
        "json":       json,
        "requests":   requests,
        "run":        run,
        "run_tool":   run_tool,
        "git_commit": git_commit,
        "TOOLS_DIR":  TOOLS_DIR,
        "FORGE_DIR":  FORGE_DIR,
        "OS":         OS,
        "DE":         DE,
        "SHELL":      SHELL,
    }

    load_tools(env)
    return env

def execute(code: str, env: dict):
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code  = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        code  = code.strip()

    try:
        exec(compile(code, "<aetherforge>", "exec"), env)
    except Exception as e:
        forge_print(f"⟁ Execution error: {e}", C.EMBER)
        dim_print(f"  Code was:\n{code}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    mode = "both"
    if "--voice" in sys.argv:
        mode = "voice"
    elif "--text" in sys.argv:
        mode = "text"

    boot_animation()
    setup_dirs()

    model = find_model()
    if not model:
        forge_print("⟁ No Qwen model found. Check your models directory.", C.EMBER)
        sys.exit(1)

    dim_print(f"  Found model: {Path(model).name}")

    if not start_llama_server(model):
        forge_print("⟁ Could not start llama-server. Exiting.", C.EMBER)
        sys.exit(1)

    atexit.register(stop_llama_server)
    signal.signal(signal.SIGINT,  lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    find_whisper()

    print()
    dim_print(f"  OS: {OS}  |  Shell: {SHELL}  |  Session: {DE or 'tty'}")
    dim_print(f"  Tools: {len(list_tools())} loaded")
    dim_print(f"  Voice: {'ready' if WHISPER_BIN and WHISPER_MODEL else 'unavailable'}")
    print()
    forge_print("⟁ Æther Forge is awake.\n")

    if not (WHISPER_BIN and WHISPER_MODEL):
        mode = "text"

    env = make_env()

    while True:
        try:
            user_input = None

            if mode == "voice":
                user_input = get_voice_input()
            elif mode == "text":
                raw = input(f"{C.AMBER}⟁ {C.RESET}")
                user_input = raw.strip() or None
            else:
                raw = input(f"{C.AMBER}⟁ {C.RESET}[v=voice] ")
                if raw.strip().lower() == "v":
                    user_input = get_voice_input()
                else:
                    user_input = raw.strip() or None

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                forge_print("⟁ Forge cooling down. Farewell.", C.DIM)
                break

            code = ask_qwen(user_input)
            if code:
                execute(code, env)
                load_tools(env)

        except KeyboardInterrupt:
            print()
            forge_print("⟁ Forge cooling down. Farewell.", C.DIM)
            break
        except Exception as e:
            forge_print(f"⟁ Loop error: {e}", C.EMBER)

if __name__ == "__main__":
    main()