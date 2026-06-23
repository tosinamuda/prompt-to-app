"""Prompt-to-applet retrieval — find an already-compiled app for a new prompt.

Makes "reusable micro-applications" real rather than rhetorical: before compiling a
fresh app, check whether a similar prompt has already been compiled and offer to reuse it.

Uses fastembed (ONNX MiniLM-L6-v2) for semantic similarity — catches paraphrases that
lexical matching misses.  Falls back to token-cosine if the embedding model fails to load.
"""

from __future__ import annotations

import logging
import math
import re

import numpy as np
from fastembed import TextEmbedding
from pydantic import BaseModel

from prompt2app import app_store

log = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "the", "to", "for", "of", "and", "or", "with", "in", "on", "at", "by",
    "is", "are", "be", "as", "that", "this", "it", "from", "into", "please", "write",
    "create", "make", "draft", "generate", "i", "want", "need", "me", "my", "we", "our",
}

# Default similarity cut-off for the semantic path, calibrated in
# scripts/calibrate_retrieval.py: paraphrases score >=0.76, unrelated prompts <=0.60,
# so 0.68 sits in the gap. (The old 0.5 admitted unrelated prompts as matches.)
SEMANTIC_MIN_SCORE = 0.68

_embedder: TextEmbedding | None = None
_embed_failed = False
_corpus_cache: dict[str, np.ndarray] = {}


def _get_embedder() -> TextEmbedding | None:
    global _embedder, _embed_failed
    if _embed_failed:
        return None
    if _embedder is None:
        try:
            _embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
        except Exception:
            log.warning("Failed to load embedding model; falling back to lexical", exc_info=True)
            _embed_failed = True
            return None
    return _embedder


def _embed(texts: list[str]) -> np.ndarray:
    emb = _get_embedder()
    if emb is None:
        raise RuntimeError("no embedder")
    return np.array(list(emb.embed(texts)))


def _embed_corpus(texts: list[str]) -> np.ndarray:
    """Embed stored-app prompts, reusing cached vectors so a stable corpus is embedded once.

    Keyed by prompt text, so an edited prompt re-embeds and an unchanged one is free —
    the query keeps repeated retrieval near O(1) in the corpus size.
    """
    missing = [t for t in dict.fromkeys(texts) if t not in _corpus_cache]
    if missing:
        for text, vec in zip(missing, _embed(missing), strict=True):
            _corpus_cache[text] = vec
    return np.array([_corpus_cache[t] for t in texts])


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# --- lexical fallback (kept for tests and degraded mode) ---


def tokenize(text: object) -> list[str]:
    return [t for t in _TOKEN.findall(str(text).lower()) if t not in _STOP and len(t) > 1]


def _counts(tokens: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tokens:
        out[t] = out.get(t, 0) + 1
    return out


def similarity(a: str, b: str) -> float:
    """Cosine similarity of token-frequency vectors, in [0, 1]."""
    va, vb = _counts(tokenize(a)), _counts(tokenize(b))
    if not va or not vb:
        return 0.0
    dot = sum(va[t] * vb.get(t, 0) for t in va)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class AppMatch(BaseModel):
    app_id: str
    title: str
    task_name: str
    score: float
    source_prompt: str


def find_similar(
    prompt: str, *, k: int = 3, min_score: float = SEMANTIC_MIN_SCORE,
) -> list[AppMatch]:
    """Top-k previously compiled apps whose source prompt is similar to `prompt`."""
    apps = [a for a in app_store.all_apps() if (a.source_prompt or "").strip()]
    if not apps:
        return []

    try:
        return _find_semantic(prompt, apps, k=k, min_score=min_score)
    except Exception:
        log.debug("Semantic retrieval unavailable; using lexical fallback", exc_info=True)
        return _find_lexical(prompt, apps, k=k, min_score=min_score)


def _find_semantic(
    prompt: str, apps: list, *, k: int, min_score: float
) -> list[AppMatch]:
    query_vec = _embed([prompt])[0]
    app_vecs = _embed_corpus([a.source_prompt for a in apps])

    matches: list[AppMatch] = []
    for i, app in enumerate(apps):
        score = _cosine(query_vec, app_vecs[i])
        if score >= min_score:
            matches.append(
                AppMatch(
                    app_id=app.app_id,
                    title=app.title,
                    task_name=app.task_name,
                    score=round(score, 3),
                    source_prompt=app.source_prompt,
                )
            )
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:k]


def _find_lexical(
    prompt: str, apps: list, *, k: int, min_score: float
) -> list[AppMatch]:
    matches: list[AppMatch] = []
    for app in apps:
        score = similarity(prompt, app.source_prompt)
        if score >= min_score:
            matches.append(
                AppMatch(
                    app_id=app.app_id,
                    title=app.title,
                    task_name=app.task_name,
                    score=round(score, 3),
                    source_prompt=app.source_prompt,
                )
            )
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:k]
