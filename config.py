"""
Æther Forge — Configuration
All constants, paths, and environment detection.
"""

import os
import platform
from pathlib import Path

# ─── Server ───────────────────────────────────────────────────────────────────

LLAMA_SERVER_URL = "http://localhost:8080"
LLAMA_PORT       = 8080
MODEL_CTX        = 2048

# ─── Paths ────────────────────────────────────────────────────────────────────

FORGE_DIR = Path.home() / ".aetherforge"
TOOLS_DIR = FORGE_DIR / "tools"

MODEL_SEARCH_DIRS = [
    Path.home() / "Documents" / "Ai_Models",
    Path.home() / "Documents" / "AI_Models",
    Path.home() / "Models",
    Path.home() / "models",
    Path.home() / ".local" / "share" / "models",
    Path.home() / "Downloads",
]

# ─── Environment ──────────────────────────────────────────────────────────────

OS    = platform.system()
DE    = os.environ.get("XDG_SESSION_TYPE", "").lower()
SHELL = "powershell" if OS == "Windows" else "bash"

# ─── Voice ────────────────────────────────────────────────────────────────────

PTT_KEY      = "V"
RECORD_SECS  = 6
SAMPLE_RATE  = 16000

WHISPER_MODEL_PATHS = [
    Path.home() / "home" / "Camilla" / ".aetherforge" / "models",
    Path("/home/Camilla/.aetherforge/models"),
    Path("/home/Camilla/.aetherforge/models"),
    FORGE_DIR / "models",
]

WHISPER_PREFERRED = [
    "ggml-base.en.bin",
    "ggml-small.en.bin",
    "ggml-tiny.en.bin",
]