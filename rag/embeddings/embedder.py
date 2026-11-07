"""Local embedding model using Sentence Transformers.

Uses all-MiniLM-L6-v2 by default — a fast, lightweight model that runs on CPU.
Never uses OpenAI embeddings. The model is downloaded once and cached locally.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import get_settings

settings = get_settings()
log = logging.getLogger("rag.embeddings.embedder")

_model = None


def get_embedder():
    """Get the cached SentenceTransformer model instance."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.RAG_EMBEDDING_MODEL, device="cpu")
        log.info("embedding model loaded: %s", settings.RAG_EMBEDDING_MODEL)
        return _model
    except Exception as exc:
        log.error("failed to load embedding model: %s", exc)
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings. Returns a list of embedding vectors."""
    model = get_embedder()
    if model is None:
        raise RuntimeError("Embedding model not available")
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
