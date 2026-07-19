"""
Æther Forge — Server
llama-server lifecycle: find, start, health check, stop.
"""

import subprocess
from pathlib import Path
from config import OS, LLAMA_SERVER_URL, LLAMA_PORT, MODEL_CTX, FORGE_DIR
from ui.terminal import forge_print, dim_print, C

LLAMA_PROC = None

# ─── Model detection ──────────────────────────────────────────────────────────

def find_model(search_dirs: list[Path]) -> str | None:
    for d in search_dirs:
        if d.exists():
            candidates = sorted(d.glob("*.gguf"), reverse=True)
            for f in candidates:
                if "qwen" in f.name.lower():
                    return str(f)
    return None

# ─── Server ───────────────────────────────────────────────────────────────────

def find_llama_server() -> str | None:
    for name in ["llama-server", "llama_server"]:
        cmd = ["where", name] if OS == "Windows" else ["which", name]
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

def start(model_path: str) -> bool:
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

    log = open(FORGE_DIR / "llama-server.log", "w")
    LLAMA_PROC = subprocess.Popen(
        [binary, "-m", model_path, "--port", str(LLAMA_PORT), "-c", str(MODEL_CTX)],
        stdout=log, stderr=log,
        start_new_session=True
    )

    forge_print("⟁ Waiting for model to load", C.DIM, end="", flush=True)
    import time
    for _ in range(60):
        if server_healthy():
            print(f" {C.AMBER}ready.{C.RESET}")
            return True
        print(f"{C.DIM}.{C.RESET}", end="", flush=True)
        time.sleep(1)

    print()
    forge_print("⟁ llama-server failed to start. Check ~/.aetherforge/llama-server.log", C.EMBER)
    return False

def stop():
    global LLAMA_PROC
    if LLAMA_PROC and LLAMA_PROC.poll() is None:
        forge_print("\n⟁ Shutting down llama-server...", C.DIM)
        LLAMA_PROC.terminate()
        try:
            LLAMA_PROC.wait(timeout=5)
        except subprocess.TimeoutExpired:
            LLAMA_PROC.kill()