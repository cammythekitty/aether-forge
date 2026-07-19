"""
Æther Forge — Tools
Load, list, and manage self-written tools.
"""

import importlib.util
import subprocess
from pathlib import Path
from config import TOOLS_DIR, FORGE_DIR
from ui.terminal import forge_print, dim_print, C

# ─── List ─────────────────────────────────────────────────────────────────────

def list_tools() -> list[str]:
    if not TOOLS_DIR.exists():
        return []
    return [f.stem for f in TOOLS_DIR.glob("*.py")]

# ─── Load ─────────────────────────────────────────────────────────────────────

def load_tools(env: dict):
    for tool_file in TOOLS_DIR.glob("*.py"):
        try:
            spec   = importlib.util.spec_from_file_location(tool_file.stem, tool_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            env[tool_file.stem] = module
        except Exception as e:
            dim_print(f"  Could not load tool {tool_file.stem}: {e}")

# ─── Run ──────────────────────────────────────────────────────────────────────

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

# ─── Git ──────────────────────────────────────────────────────────────────────

def git_commit(message: str):
    subprocess.run(["git", "-C", str(TOOLS_DIR), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(TOOLS_DIR), "commit", "-m", message], capture_output=True)
    forge_print(f"⟁ Committed: {message}", C.DIM)

# ─── Setup ────────────────────────────────────────────────────────────────────

def setup():
    FORGE_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    if not (TOOLS_DIR / ".git").exists():
        subprocess.run(["git", "init", str(TOOLS_DIR)], capture_output=True)
        readme = TOOLS_DIR / "README.md"
        readme.write_text("# Æther Forge — Tools\nThis directory is owned by Æther Forge. Tools are written and committed automatically.\n")
        subprocess.run(["git", "-C", str(TOOLS_DIR), "add", "."], capture_output=True)
        subprocess.run(["git", "-C", str(TOOLS_DIR), "commit", "-m", "Initial forge — Æther Forge awakens"], capture_output=True)
        forge_print("⟁ Tools directory initialised.") 