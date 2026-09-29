"""Generates the actual image bytes for a VisualPrompt, via Gemini's
image-generation models over the same google-genai client/API key already
used for question generation and embeddings.

Needs an API key with billing enabled: Gemini image models have no free
tier at all (text generation works fine on free tier - only this call
needs the paid tier). Until billing is on, this raises, which callers
already treat as a normal per-item failure (see _resolve_grid_layout in
question_generation.py - one bad/failed image just gets left with
image_id=None rather than aborting the whole worksheet).

Model choice: gemini-3.1-flash-lite-image, not the (cheaper-sounding but
irrelevant) 2.5 generation - gemini-2.5-flash-image is deprecated and
Google shuts it down 2026-10-02. The "lite" 3.1 variant is the cheapest
current option; swap to gemini-3.1-flash-image if illustration quality
needs to go up.
"""

import httpx
from google.genai import errors, types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.llm import get_genai_client

IMAGE_MODEL = "gemini-3.1-flash-lite-image"


class ImageGenerationError(Exception):
    pass


@retry(
    retry=retry_if_exception_type((errors.ServerError, errors.APIError, httpx.TransportError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def generate_image(prompt: str) -> bytes:
    """Calls Gemini's image model with `prompt` and returns PNG (or
    whatever mime type it responds with) bytes from the first image part
    in the response. Raises ImageGenerationError if the response has no
    image part at all (e.g. the model responded with only text)."""
    client = get_genai_client()
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    candidates = response.candidates or []
    for candidate in candidates:
        parts = candidate.content.parts if candidate.content else []
        for part in parts or []:
            if part.inline_data is not None and part.inline_data.data:
                return part.inline_data.data

    raise ImageGenerationError(f"No image returned for prompt: {prompt!r}")
