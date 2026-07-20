"""
Æther Forge — Brain
Loads system prompt from file and handles Qwen communication.
"""

from pathlib import Path
from config import LLAMA_SERVER_URL, OS, DE, SHELL, TOOLS_DIR

# ─── System prompt ────────────────────────────────────────────────────────────

from string import Template
PROMPT_FILE = Path(__file__).parent.parent / "system_prompt.txt"

def build_system_prompt(tools: list[str]) -> str:
    tools_str = "\n".join(f"  - {t}" for t in tools) if tools else "  (none yet)"

    platform_notes = []
    if DE == "wayland":
        platform_notes.append("Use ydotool for simulating keypresses on Wayland.")
    elif DE == "x11":
        platform_notes.append("Use xdotool for keypresses on X11.")
    if OS == "Windows":
        platform_notes.append("Use PowerShell syntax for shell commands.")

    try:
        template = PROMPT_FILE.read_text()
    except FileNotFoundError:
        raise FileNotFoundError(f"system_prompt.txt not found at {PROMPT_FILE}")

    return Template(template).substitute(
        OS=OS,
        SHELL=SHELL,
        DE=DE or "tty",
        WAYLAND="yes" if DE == "wayland" else "no",
        TOOLS_DIR=TOOLS_DIR,
        TOOLS=tools_str,
        PLATFORM_NOTES="\n  ".join(platform_notes) if platform_notes else "Standard Linux environment.",
    )

# ─── Qwen call ────────────────────────────────────────────────────────────────

def ask(user_input: str, tools: list[str]) -> str | None:
    try:
        import requests
        from ui.terminal import forge_print, C
 
        payload = {
            "model": "qwen",
            "messages": [
                {"role": "system", "content": build_system_prompt(tools)},
                {"role": "user",   "content": user_input}
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "stream": False
        }

        forge_print("⟁ Forging...", C.DIM)
        resp = requests.post(
            f"{LLAMA_SERVER_URL}/v1/chat/completions",
            json=payload, timeout=None
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        from ui.terminal import forge_print, C
        forge_print(f"⟁ Brain error: {e}", C.EMBER)
        return None