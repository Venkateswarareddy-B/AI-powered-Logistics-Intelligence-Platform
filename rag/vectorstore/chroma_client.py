"""ChromaDB vector store client.

Provides a thin wrapper around ChromaDB for storing and retrieving
document chunks with their embeddings. Uses local persistent storage.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from backend.core.config import get_settings

settings = get_settings()
log = logging.getLogger("rag.vectorstore.chroma_client")

COLLECTION_NAME = "yottaflex_policies"
_client = None
_collection = None


def get_client():
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is not None:
        return _client
    persist_dir = settings.CHROMA_PERSIST_DIR
    os.makedirs(persist_dir, exist_ok=True)
    try:
        import chromadb
        _client = chromadb.PersistentClient(path=persist_dir)
        log.info("chromadb client initialized at %s", persist_dir)
        return _client
    except Exception as exc:
        log.error("failed to init chromadb: %s", exc)
        return None


def get_collection():
    """Get or create the YottaFlex policies collection."""
    global _collection
    if _collection is not None:
        return _collection
    client = get_client()
    if client is None:
        return None
    try:
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "YottaFlex logistics policy documents"},
        )
        return _collection
    except Exception as exc:
        log.error("failed to get collection: %s", exc)
        return None


def add_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
) -> int:
    """Add document chunks with embeddings to the collection.

    Each chunk dict must have: id, text, metadata (dict with document_id, etc.)
    """
    coll = get_collection()
    if coll is None:
        return 0
    coll.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
        embeddings=embeddings,
    )
    return len(chunks)


def query(
    query_embedding: list[float],
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Query the collection for similar chunks. Returns list of result dicts."""
    coll = get_collection()
    if coll is None:
        return []
    kwargs = {"query_embeddings": [query_embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    results = coll.query(**kwargs)
    items = []
    for i in range(len(results["ids"][0])):
        items.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return items


def count_chunks() -> int:
    coll = get_collection()
    if coll is None:
        return 0
    return coll.count()


def delete_by_document(document_id: str) -> int:
    """Delete all chunks belonging to a document."""
    coll = get_collection()
    if coll is None:
        return 0
    # ChromaDB doesn't have a direct delete-by-metadata, so we use where filter
    existing = coll.get(where={"document_id": document_id})
    if existing["ids"]:
        coll.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0
