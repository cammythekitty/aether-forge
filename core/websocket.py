"""
Æther Forge — WebSocket Server
Bridges the frontend GUI and the Python brain/executor pipeline.
"""

import asyncio
import json
import io
import re
import sys
import traceback
import websockets
from contextlib import redirect_stdout, redirect_stderr

WS_PORT = 7878
_clients = set()

# ─── ANSI stripping ──────────────────────────────────────────────────────────

def strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)

# ─── Output capture ──────────────────────────────────────────────────────────

class ForgeStream(io.TextIOBase):
    """Captures stdout/stderr and forwards to the websocket client."""

    def __init__(self, loop, websocket, msg_type="output"):
        self.loop      = loop
        self.websocket = websocket
        self.msg_type  = msg_type

    def write(self, text):
        clean = strip_ansi(text)
        if clean.strip():
            asyncio.run_coroutine_threadsafe(
                self._send(clean),
                self.loop
            )
        return len(text)

    async def _send(self, text):
        try:
            await self.websocket.send(json.dumps({
                "type": self.msg_type,
                "text": text
            }))
        except Exception:
            pass

    def flush(self):
        pass

# ─── Helpers ─────────────────────────────────────────────────────────────────

def clean_code(code: str) -> str:
    """Strip markdown fences from Qwen output."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code  = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return code.strip()

# ─── Handler ─────────────────────────────────────────────────────────────────

async def handle(websocket, brain_ask, executor_execute, env, list_tools, load_tools, voice_get=None):
    """Handle a single frontend connection."""
    _clients.add(websocket)
    loop = asyncio.get_event_loop()

    async def send(msg_type, text):
        try:
            await websocket.send(json.dumps({
                "type": msg_type,
                "text": strip_ansi(text)
            }))
        except Exception:
            pass

    await send("output", "⟁ Forge connected. Ready.")

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except Exception:
                continue

            msg_type = data.get("type")

            # ── Text command ──────────────────────────────────────────────
            if msg_type == "command":
                user_input = data.get("text", "").strip()
                if not user_input:
                    continue

                await asyncio.to_thread(
                    _run_command,
                    user_input,
                    loop,
                    websocket,
                    brain_ask,
                    executor_execute,
                    env,
                    list_tools,
                    load_tools
                )

                await send("done", "")

            # ── Voice ─────────────────────────────────────────────────────
            elif msg_type == "voice_start":
                if voice_get is None:
                    await send("error", "⟁ Voice unavailable.")
                    continue

                await send("output", "⟁ Listening...")
                transcript = await asyncio.to_thread(voice_get)

                if transcript:
                    await send("output", f"⟁ Heard: {transcript}")
                    await asyncio.to_thread(
                        _run_command,
                        transcript,
                        loop,
                        websocket,
                        brain_ask,
                        executor_execute,
                        env,
                        list_tools,
                        load_tools
                    )
                    await send("done", "")
                else:
                    await send("error", "⟁ Could not transcribe audio.")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _clients.discard(websocket)

def _run_command(user_input, loop, websocket, brain_ask, executor_execute, env, list_tools, load_tools):
    """Run a command synchronously, capturing all output to the websocket."""

    stdout_stream = ForgeStream(loop, websocket, "output")
    stderr_stream = ForgeStream(loop, websocket, "error")

    with redirect_stdout(stdout_stream), redirect_stderr(stderr_stream):
        try:
            code = brain_ask(user_input, list_tools())
            if code:
                cleaned = clean_code(code)

                # Send code block to frontend
                asyncio.run_coroutine_threadsafe(
                    websocket.send(json.dumps({
                        "type": "code",
                        "text": cleaned
                    })),
                    loop
                ).result()

                executor_execute(cleaned, env)
                load_tools(env)

        except Exception:
            asyncio.run_coroutine_threadsafe(
                websocket.send(json.dumps({
                    "type": "error",
                    "text": traceback.format_exc()
                })),
                loop
            ).result()

# ─── Server ──────────────────────────────────────────────────────────────────

async def serve(brain_ask, executor_execute, env, list_tools, load_tools, voice_get=None):
    async def _handler(ws):
        await handle(ws, brain_ask, executor_execute, env, list_tools, load_tools, voice_get)

    async with websockets.serve(_handler, "localhost", WS_PORT):
        print(f"\033[38;2;100;100;100m  WebSocket server on ws://localhost:{WS_PORT}\033[0m")
        await asyncio.Future()