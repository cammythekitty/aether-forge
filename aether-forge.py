#!/usr/bin/env python3
"""
Æther Forge — Powered by Vaelora Systems
A fully local AI environment that grows with you.

Usage:
  python aetherforge.py           # voice + text
  python aetherforge.py --text    # text only (hotel mode)
  python aetherforge.py --voice   # voice only
"""

import sys
import signal
import atexit
from pathlib import Path

from config import MODEL_SEARCH_DIRS, OS, DE, SHELL
from ui.terminal import boot_animation, forge_print, dim_print, C
from core.server import find_model, start, stop
from core.tools import setup, list_tools, load_tools
from core.voice import find_whisper, get_voice_input, is_ready as voice_ready
from core.brain import ask
from core.executor import make_env, execute

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    mode = "both"
    if "--voice" in sys.argv:
        mode = "voice"
    elif "--text" in sys.argv:
        mode = "text"

    # Boot
    boot_animation()
    setup()

    # Find and start model
    model = find_model(MODEL_SEARCH_DIRS)
    if not model:
        forge_print("⟁ No Qwen model found. Check your models directory.", C.EMBER)
        sys.exit(1)

    dim_print(f"  Found model: {Path(model).name}")

    if not start(model):
        forge_print("⟁ Could not start llama-server. Exiting.", C.EMBER)
        sys.exit(1)

    # Clean shutdown hooks
    atexit.register(stop)
    signal.signal(signal.SIGINT,  lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    # Voice
    find_whisper()
    if not voice_ready():
        mode = "text"

    # Status
    print()
    dim_print(f"  OS: {OS}  |  Shell: {SHELL}  |  Session: {DE or 'tty'}")
    dim_print(f"  Tools: {len(list_tools())} loaded")
    dim_print(f"  Voice: {'ready' if voice_ready() else 'unavailable'}")
    print()
    forge_print("⟁ Æther Forge is awake.\n")

    # Exec environment
    env = make_env()

    # Main loop
    while True:
        try:
            user_input = None

            if mode == "voice":
                user_input = get_voice_input()

            elif mode == "text":
                raw = input(f"{C.AMBER}⟁ {C.RESET}")
                user_input = raw.strip() or None

            else:  # both
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

if __name__ == "__main__":
    main()