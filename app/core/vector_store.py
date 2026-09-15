import threading

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings

_client: chromadb.ClientAPI | None = None
_client_lock = threading.Lock()


def get_chroma_client() -> chromadb.ClientAPI:
    """Process-wide singleton, built at most once even when the first calls
    race on different threadpool threads (e.g. a Builder 'Specific' section
    firing several /questions/generate calls in parallel). A bare
    @lru_cache does NOT prevent that race - it only locks its cache dict,
    not the wrapped call - so two first-callers could both construct a
    chromadb.PersistentClient concurrently. ChromaDB's own internal client
    registry isn't safe against that: one thread's half-built client gets
    torn down mid-init by the other, crashing with
    AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def _cache_clear() -> None:
    """Drops the singleton so the next get_chroma_client() call rebuilds it
    against (possibly new) settings - mirrors functools.lru_cache's own
    cache_clear() API, which tests/conftest.py's api_client fixture relies
    on to isolate each test's Chroma dir via a monkeypatched CHROMA_PERSIST_DIR."""
    global _client
    with _client_lock:
        _client = None


get_chroma_client.cache_clear = _cache_clear


def get_collection(subject_id: str) -> Collection:
    """Get (or create) the collection that stores syllabus chunk embeddings
    for one subject. Each subject gets its own collection so retrieval never
    surfaces content from a different subject's uploads."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=f"subject_{subject_id}",
        metadata={"hnsw:space": "cosine"},
    )
