"""
Æther Forge — Memory
Adapted from AtlasAI MemoryStore. Vector search with time decay.
"""

import os
import json
import math
import time
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

EMBED_MODEL = "all-MiniLM-L6-v2"
HALF_LIFE_SECONDS = 60 * 60 * 24 * 7  # 1 week
ENGRAM_TYPE_WEIGHTS = {
    "preference": 1.5,
    "manual":     1.4,
    "insight":    1.6,
    "web":        1.2,
    "fact":       1.0,
    "event":      1.1,
    "recent":     0.9,
}

MEMORY_DIR    = os.path.expanduser("~/.aetherforge/memory")
SESSION_FILE  = os.path.join(MEMORY_DIR, "session.txt")
LONGTERM_FILE = os.path.join(MEMORY_DIR, "longterm.jsonl")

# ─── Fallback embedding ───────────────────────────────────────────────────────

def simple_embedding(text: str, dim: int = 384) -> np.ndarray:
    vec = np.zeros(dim, dtype="float32")
    for i, ch in enumerate(text):
        vec[i % dim] += ord(ch)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec

# ─── MemoryStore ──────────────────────────────────────────────────────────────

class MemoryStore:
    def __init__(self, path: str = LONGTERM_FILE, embed_model_name: str = EMBED_MODEL):
        self.path = path
        self.embed_model_name = embed_model_name
        self.entries: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.use_fallback = False
        self.model = None

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._initialize_embedder()
        self.load()

    def _initialize_embedder(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.embed_model_name)
        except Exception:
            self.use_fallback = True

    def _embed_text(self, texts: List[str]) -> np.ndarray:
        if self.use_fallback or self.model is None:
            return np.vstack([simple_embedding(t) for t in texts]).astype("float32")
        embeddings = self.model.encode(texts, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype="float32")
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embeddings / norms

    def _build_embeddings(self) -> None:
        if not self.entries:
            self.embeddings = None
            return
        texts = [e["text"] for e in self.entries]
        self.embeddings = self._embed_text(texts)

    def add(self, text: str, tag: str = "fact", weight: float = 1.0, source: str = "") -> None:
        entry = {
            "text":      text.strip(),
            "tag":       tag,
            "weight":    float(weight),
            "source":    source,
            "timestamp": time.time(),
        }
        self.entries.append(entry)
        new_emb = self._embed_text([text.strip()])
        if self.embeddings is None:
            self.embeddings = new_emb
        else:
            self.embeddings = np.vstack([self.embeddings, new_emb])
        self.save()

    def search(self, query: str, top_k: int = 4) -> List[str]:
        if not self.entries or self.embeddings is None:
            return []
        query_emb = self._embed_text([query])[0]
        scores = np.dot(self.embeddings, query_emb)
        now = time.time()
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for i, sim in enumerate(scores.tolist()):
            entry = self.entries[i]
            age = now - entry.get("timestamp", now)
            decay = math.exp(-age / HALF_LIFE_SECONDS)
            type_weight = ENGRAM_TYPE_WEIGHTS.get(entry.get("tag", "fact"), 1.0)
            weight = float(entry.get("weight", 1.0)) * type_weight
            scored.append((float(sim) * weight * decay, entry))

        all_scores = [s for s, _ in scored]
        mean = float(np.mean(all_scores))
        std  = float(np.std(all_scores))
        threshold = max(0.05, mean + 0.3 * std)

        scored = [(s, e) for s, e in scored if s > threshold]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [e["text"] for _, e in scored[:top_k]]

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            for entry in self.entries:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load(self) -> None:
        self.entries = []
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line.strip())
                    if isinstance(entry, dict) and "text" in entry:
                        entry.setdefault("tag", "fact")
                        entry.setdefault("weight", 1.0)
                        entry.setdefault("source", "")
                        entry.setdefault("timestamp", time.time())
                        self.entries.append(entry)
                except json.JSONDecodeError:
                    continue
        self._build_embeddings()

# ─── Module-level API (used by aetherforge.py) ────────────────────────────────

_store: Optional[MemoryStore] = None

def _get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store

def save_session(text: str) -> None:
    """Save the full session transcript to session.txt."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(text)

def extract_memory(text: str) -> None:
    """Extract facts from session text and add to long-term memory."""
    store = _get_store()
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) > 10:
            store.add(line, tag="recent")

def recall(query: str, top_k: int = 4) -> List[str]:
    """Return the most relevant memories for a given query."""
    return _get_store().search(query, top_k=top_k)

def remember(text: str, tag: str = "fact", weight: float = 1.0) -> None:
    """Manually add a memory with a specific tag and weight."""
    _get_store().add(text, tag=tag, weight=weight)