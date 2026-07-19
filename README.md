# Æther Forge
### Powered by Vaelora Systems
*A fully local AI environment that grows with you.*

---

## What it is

Æther Forge is a self-evolving local AI assistant that controls your computer via voice or text. It runs 100% offline using Qwen2.5 via llama.cpp, with no cloud, no API keys, and no restrictions.

Every complex task it performs, it saves as a reusable tool — committed to git automatically. Over time it learns your workflow and gets faster at the things you do most.

---

## Requirements

- Arch Linux (or any Linux with Wayland/X11) or Windows
- llama.cpp (`llama-server` in PATH)
- whisper-cpp (`whisper-cli` in PATH) — optional, for voice
- A Qwen GGUF model in one of the searched directories
- Python 3.11+

---

## Install

```bash
git clone https://github.com/vaelora/aether-forge
cd aether-forge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install requests sounddevice numpy scipy pynput gitpython
```

---

## Usage

```bash
source .venv/bin/activate
python aetherforge.py           # voice + text
python aetherforge.py --text    # text only
python aetherforge.py --voice   # voice only
```

Æther Forge will automatically find your Qwen model and start llama-server.

Push-to-talk: hold the **`** key (left of Z on UK keyboard) to speak.

---

## Structure

```
aetherforge/
├── aetherforge.py      ← entry point
├── config.py           ← paths, constants, environment detection
├── core/
│   ├── brain.py        ← Qwen system prompt + llama.cpp comms
│   ├── executor.py     ← Python exec environment
│   ├── server.py       ← llama-server lifecycle
│   ├── tools.py        ← tool loading, git commits
│   └── voice.py        ← whisper STT + push-to-talk
└── ui/
    └── terminal.py     ← colours, boot animation
```

---

## Self-upgrade

When Æther Forge performs a complex or repetitive task, it writes a reusable Python tool, saves it to `~/.aetherforge/tools/`, and commits it to git with a message it wrote itself.

```bash
git -C ~/.aetherforge/tools log --oneline
```

---

*Vaelora Systems — building intelligent tools for the people who build everything else.*