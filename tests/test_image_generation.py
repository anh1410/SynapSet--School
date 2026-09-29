"""Unit tests mock the Gemini client to test generate_image's response-parsing
logic without hitting the network. The real end-to-end call is exercised in
tests/test_llm_integration.py (llm-marked, excluded from the default run)."""

from types import SimpleNamespace

import pytest

from app.services.image_generation import ImageGenerationError, generate_image


def _fake_client(response):
    return SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))


def _image_part(data: bytes = b"\x89PNG\r\n\x1a\nfakepngbytes"):
    return SimpleNamespace(inline_data=SimpleNamespace(data=data, mime_type="image/png"), text=None)


def _text_part(text: str = "I can't generate that."):
    return SimpleNamespace(inline_data=None, text=text)


def test_generate_image_extracts_inline_data(monkeypatch):
    response = SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[_text_part(), _image_part(b"real-bytes")]))]
    )
    monkeypatch.setattr(
        "app.services.image_generation.get_genai_client", lambda: _fake_client(response)
    )

    result = generate_image("a cartoon frog")

    assert result == b"real-bytes"


def test_generate_image_raises_when_no_image_part(monkeypatch):
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[_text_part()]))])
    monkeypatch.setattr(
        "app.services.image_generation.get_genai_client", lambda: _fake_client(response)
    )

    with pytest.raises(ImageGenerationError):
        generate_image("a cartoon frog")


def test_generate_image_raises_when_no_candidates(monkeypatch):
    response = SimpleNamespace(candidates=[])
    monkeypatch.setattr(
        "app.services.image_generation.get_genai_client", lambda: _fake_client(response)
    )

    with pytest.raises(ImageGenerationError):
        generate_image("a cartoon frog")
