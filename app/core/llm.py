import time
from functools import lru_cache

import httpx
from google import genai
from google.genai import errors
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

# Free-tier rate limits are per-minute; a short retry budget (the previous
# stop_after_attempt=4 / max wait=30s, ~14s of cumulative backoff) can burn
# out before a per-minute window actually resets. This budget waits up to
# ~2m across 6 attempts, long enough to cross a full RPM window at least
# once instead of giving up mid-window.
_RATE_LIMIT_RETRY = dict(
    retry=retry_if_exception_type((errors.ServerError, errors.APIError, httpx.TransportError)),
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)


@lru_cache
def get_genai_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.google_api_key)


@retry(**_RATE_LIMIT_RETRY)
def embed_text(text: str) -> list[float]:
    settings = get_settings()
    client = get_genai_client()
    result = client.models.embed_content(model=settings.embedding_model, contents=text)
    return result.embeddings[0].values


# embed_content accepts a list[str] and returns one embedding per text in
# the same order, in a single API call - chosen conservatively below the
# API's actual batch cap so one oversized document still splits cleanly.
_EMBED_BATCH_SIZE = 50


@retry(**_RATE_LIMIT_RETRY)
def _embed_batch(client: genai.Client, model: str, batch: list[str]) -> list[list[float]]:
    """Retries per-batch, not per whole-document call - a failure on batch 3
    of 5 shouldn't force re-embedding (and re-spending quota on) batches 1-2
    that already succeeded."""
    result = client.models.embed_content(model=model, contents=batch)
    return [e.values for e in result.embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batches embedding calls instead of one call per text. Ingesting even
    a modest ~20-page document chunks into 15-20+ retrieval chunks
    (document_extraction.py's chunk_size=800), and firing that many
    embed_text() calls back-to-back with no pacing reliably blows through
    the Gemini free tier's per-minute rate limit - confirmed via a real
    ingestion failure (429 RESOURCE_EXHAUSTED). Batching collapses that
    burst to ~1 call per _EMBED_BATCH_SIZE chunks; a short pause between
    batches (only relevant for a document big enough to need more than one)
    adds further headroom against the same limit."""
    if not texts:
        return []
    settings = get_settings()
    client = get_genai_client()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        if i > 0:
            time.sleep(2)
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        embeddings.extend(_embed_batch(client, settings.embedding_model, batch))
    return embeddings
