"""
Æther Forge — Terminal UI
Colours, boot animation, print helpers.
"""

import os
import time
from config import OS

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

def clear():
    os.system("clear" if OS != "Windows" else "cls")

# ─── Runes ────────────────────────────────────────────────────────────────────

RUNES = ["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚷ", "ᚹ", "ᛁ", "ᛃ", "ᛇ", "ᛚ", "ᛟ"]

def _render_runes(lit: list[str]):
    print("\n\n")
    print("        " + "  ".join(lit[:6]))
    print("        " + "  ".join(lit[6:]))

def boot_animation():
    clear()

    # Light up clockwise
    for i in range(len(RUNES)):
        clear()
        lit = [
            f"{C.AMBER}{C.BOLD}{r}{C.RESET}" if j <= i else f"{C.DIM}{r}{C.RESET}"
            for j, r in enumerate(RUNES)
        ]
        _render_runes(lit)
        time.sleep(0.12)

    time.sleep(0.4)

    # Sweep — 180 degree fade
    for i in range(len(RUNES)):
        clear()
        lit = [
            f"{C.DIM}{r}{C.RESET}" if j <= i else f"{C.AMBER}{C.BOLD}{r}{C.RESET}"
            for j, r in enumerate(RUNES)
        ]
        _render_runes(lit)
        time.sleep(0.06)

    # Settle into corner
    clear()
    corner = f"{C.DIM}{'  '.join(RUNES[:6])}{C.RESET}"
    print(f"  {corner}\n")
    print(f"{C.AMBER}{C.BOLD}        Æ T H E R  F O R G E{C.RESET}")
    print(f"{C.DIM}        A fully local AI environment that grows with you.{C.RESET}")
    print(f"{C.DIM}        Powered by Vaelora Systems{C.RESET}")
    print()