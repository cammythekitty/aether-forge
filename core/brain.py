"""
Æther Forge — Brain
Qwen system prompt construction and llama.cpp communication.
"""

from config import LLAMA_SERVER_URL, OS, DE, SHELL, TOOLS_DIR
from ui.terminal import forge_print, C

# ─── System prompt ────────────────────────────────────────────────────────────

def build_system_prompt(tools: list[str]) -> str:
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

# ─── Qwen call ────────────────────────────────────────────────────────────────

def ask(user_input: str, tools: list[str]) -> str | None:
    try:
        import requests

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
            json=payload, timeout=120
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        forge_print(f"⟁ Brain error: {e}", C.EMBER)
        return None