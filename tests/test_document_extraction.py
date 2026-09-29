from pathlib import Path

import pytest

from app.services.document_extraction import (
    _is_garbled,
    chunk_text,
    extract_and_chunk,
    extract_and_chunk_for_extraction,
    extract_text,
    extract_text_from_pdf,
    extract_text_from_pptx,
)

SAMPLE_PPTX = Path("data/uploads/CC/unit1.pptx")
SAMPLE_PDF = Path("data/uploads/CC/unit1QB.pdf")


def test_extract_and_chunk_skips_extraction_when_text_given(monkeypatch):
    def fail_if_called(path):
        raise AssertionError("extract_text should not be called when text= is given")

    monkeypatch.setattr("app.services.document_extraction.extract_text", fail_if_called)

    chunks = extract_and_chunk("fake.pdf", text="hello world " * 50)
    assert len(chunks) >= 1

    chunks2 = extract_and_chunk_for_extraction("fake.pdf", text="hello world " * 50)
    assert len(chunks2) >= 1


def test_is_garbled_detects_legacy_font_mojibake():
    # Real extracted text from a PDF typeset in the legacy Nudi Kannada font.
    garbled = "PÀ£ÁðlPÀ ¸ÀPÁðgÀ ¹j PÀ£ÀßqÀ ¥ÀæxÀªÀÄ ¨sÁµÉ PÀ£ÀßqÀ ¥ÀoÀå¥ÀÄ¸ÀÛPÀ eÁÕ£À ¸ÀAWÀ"
    assert _is_garbled(garbled) is True


def test_is_garbled_false_for_real_english():
    text = "Photosynthesis is the process by which green plants convert sunlight into chemical energy for growth."
    assert _is_garbled(text) is False


def test_is_garbled_false_for_real_kannada_unicode():
    text = "ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು? ಸಸ್ಯಗಳು ಸೂರ್ಯನ ಬೆಳಕನ್ನು ಬಳಸಿಕೊಂಡು ಆಹಾರ ತಯಾರಿಸುತ್ತವೆ."
    assert _is_garbled(text) is False


def test_is_garbled_false_for_too_little_text():
    # Can't judge reliably on a handful of characters either way - default to "not garbled"
    # rather than trigger OCR (slow, model download) on effectively-empty extraction.
    assert _is_garbled("À Á ð") is False


def test_chunk_text_basic():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, source_document="test.txt", chunk_size=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert all(c.source_document == "test.txt" for c in chunks)


def test_chunk_text_overlap():
    text = " ".join(f"w{i}" for i in range(30))
    chunks = chunk_text(text, source_document="t", chunk_size=10, overlap=3)
    assert chunks[0].text.split()[-3:] == chunks[1].text.split()[:3]


def test_chunk_text_empty():
    assert chunk_text("", source_document="t") == []


def test_extract_text_unsupported_extension(tmp_path):
    path = tmp_path / "file.xyz"
    path.write_text("hello")
    with pytest.raises(ValueError):
        extract_text(str(path))


def test_extract_text_legacy_ppt_rejected(tmp_path):
    path = tmp_path / "file.ppt"
    path.write_bytes(b"fake")
    with pytest.raises(ValueError, match="Legacy .ppt"):
        extract_text(str(path))


@pytest.mark.skipif(not SAMPLE_PPTX.exists(), reason="sample course file not present locally")
def test_extract_real_pptx():
    text = extract_text_from_pptx(str(SAMPLE_PPTX))
    assert len(text) > 500


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample course file not present locally")
def test_extract_real_pdf():
    text = extract_text_from_pdf(str(SAMPLE_PDF))
    assert len(text) > 100
