#!/usr/bin/env python3
"""
Æther Forge — Powered by Vaelora Systems
A fully local AI environment that grows with you.

Usage:
  python aetherforge.py           # voice + text (terminal)
  python aetherforge.py --text    # text only (hotel mode)
  python aetherforge.py --voice   # voice only
  python aetherforge.py --gui     # GUI mode (websocket server)
"""

import sys
import signal
import asyncio
import atexit
from pathlib import Path

from config import MODEL_SEARCH_DIRS, OS, DE, SHELL
from ui.terminal import boot_animation, forge_print, dim_print, C
from core.server import find_model, start, stop
from core.tools import setup, list_tools, load_tools
from core.voice import find_whisper, get_voice_input, is_ready as voice_ready
from core.brain import ask
from core.executor import make_env, execute

# ─── Shared startup ───────────────────────────────────────────────────────────

def startup() -> dict | None:
    boot_animation()
    setup()

    model = find_model(MODEL_SEARCH_DIRS)
    if not model:
        forge_print("⟁ No Qwen model found. Check your models directory.", C.EMBER)
        return None

    dim_print(f"  Found model: {Path(model).name}")

    if not start(model):
        forge_print("⟁ Could not start llama-server. Exiting.", C.EMBER)
        return None

    atexit.register(stop)
    signal.signal(signal.SIGINT,  lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    find_whisper()

    print()
    dim_print(f"  OS: {OS}  |  Shell: {SHELL}  |  Session: {DE or 'tty'}")
    dim_print(f"  Tools: {len(list_tools())} loaded")
    dim_print(f"  Voice: {'ready' if voice_ready() else 'unavailable'}")
    print()

    return make_env()

# ─── GUI mode ─────────────────────────────────────────────────────────────────

def run_gui(env: dict):
    from core.websocket import serve

    forge_print("⟁ GUI mode — starting WebSocket server...", C.AMBER)
    forge_print("⟁ Open the frontend at http://localhost:5173\n", C.DIM)

    voice = get_voice_input if voice_ready() else None

    asyncio.run(serve(
        brain_ask        = ask,
        executor_execute = execute,
        env              = env,
        list_tools       = list_tools,
        load_tools       = load_tools,
        voice_get        = voice,
    ))

# ─── Terminal mode ────────────────────────────────────────────────────────────

def run_terminal(env: dict, mode: str):
    forge_print("⟁ Æther Forge is awake.\n")

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

            code = ask(user_input, list_tools())
            if code:
                execute(code, env)
                load_tools(env)

        except KeyboardInterrupt:
            print()
            forge_print("⟁ Forge cooling down. Farewell.", C.DIM)
            break
        except Exception as e:
            forge_print(f"⟁ Loop error: {e}", C.EMBER)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    gui   = "--gui"   in sys.argv
    voice = "--voice" in sys.argv
    text  = "--text"  in sys.argv

    env = startup()
    if env is None:
        sys.exit(1)

    if gui:
        run_gui(env)
    else:
        mode = "voice" if voice else "text" if text else "both"
        if not voice_ready():
            mode = "text"
        run_terminal(env, mode)

if __name__ == "__main__":
    main()