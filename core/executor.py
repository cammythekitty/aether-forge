"""
Æther Forge — Executor
Python exec environment and code execution.
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from config import TOOLS_DIR, FORGE_DIR, OS, DE, SHELL
from core.tools import load_tools, run_tool, git_commit
from ui.terminal import forge_print, dim_print, C

# ─── Environment ──────────────────────────────────────────────────────────────

def make_env() -> dict:
    import requests

    def run(cmd: str) -> str:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out = (result.stdout + result.stderr).strip()
        if out:
            print(out)
        return out

    env = {
        # stdlib
        "os":         os,
        "sys":        sys,
        "subprocess": subprocess,
        "Path":       Path,
        "time":       time,
        "json":       json,
        "requests":   requests,
        # helpers
        "run":        run,
        "run_tool":   run_tool,
        "git_commit": git_commit,
        # paths + context
        "TOOLS_DIR":  TOOLS_DIR,
        "FORGE_DIR":  FORGE_DIR,
        "OS":         OS,
        "DE":         DE,
        "SHELL":      SHELL,
    }

    load_tools(env)
    return env

# ─── Execute ──────────────────────────────────────────────────────────────────

def execute(code: str, env: dict):
    code = code.strip()

    # Strip accidental markdown fences
    if code.startswith("```"):
        lines = code.split("\n")
        code  = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        code  = code.strip()

    try:
        exec(compile(code, "<aetherforge>", "exec"), env)

    except FileNotFoundError as e:
        import re
        match = re.search(r"'([^']+)'", str(e))
        if match:
            binary = match.group(1)
            if '/' in binary or binary.endswith('.py'):
                forge_print(f"⟁ File not found: {binary}", C.EMBER)
            else:
                forge_print(f"⟁ Missing: {binary}, installing...", C.DIM)
                result = subprocess.run(
                    ["sudo", "pacman", "-S", "--noconfirm", binary],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    forge_print(f"⟁ Installed {binary}, retrying...", C.DIM)
                    exec(compile(code, "<aetherforge>", "exec"), env)
                else:
                    forge_print(f"⟁ Could not install {binary}", C.EMBER)

    except Exception as e:
        forge_print(f"⟁ Execution error: {e}", C.EMBER)
        dim_print(f"  Code was:\n{code}")