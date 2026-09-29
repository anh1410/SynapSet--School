from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation
from pypdf import PdfReader

from app.services.indic_text import _SCRIPT_RANGES


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    source_document: str
    page_number: int | None = None


# Indian government/textbook PDFs are very often typeset with a legacy
# pre-Unicode Indic font (Nudi for Kannada, Kruti Dev/DevLys for Hindi,
# etc). The PDF renders correctly on screen because the embedded font
# draws real Kannada/Devanagari glyphs, but the text LAYER stores
# arbitrary byte codes with no real ToUnicode mapping - extracting "text"
# from it yields Latin-1/Latin-Extended mojibake, not the actual script.
# Confirmed empirically: this ratio is ~0% for real English and real
# Kannada/Devanagari Unicode text, and ~66% for a real garbled Nudi PDF.
_GARBLED_LATIN_EXTENDED_RATIO = 0.15


def _is_garbled(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 50:  # too little text to judge reliably either way
        return False
    suspicious = sum(1 for c in letters if 0x0080 <= ord(c) <= 0x024F)
    return suspicious / len(letters) > _GARBLED_LATIN_EXTENDED_RATIO


# EasyOCR refuses to combine Kannada with anything but English in one
# Reader ("Kannada is only compatible with English") - Hindi (Devanagari)
# is separately English-only too - so a single ["en","hi","kn"] reader
# doesn't exist; two single-script readers are needed instead. Which one
# applies isn't known ahead of time (a garbled PDF gives no language hint),
# so _ocr_pdf runs both and keeps whichever actually recognized more
# target-script text.
_OCR_LANGUAGE_SETS: dict[str, list[str]] = {
    "devanagari": ["en", "hi"],
    "kannada": ["en", "kn"],
}


@lru_cache
def _ocr_reader(langs: tuple[str, ...]):
    """Loaded once per process per language set - EasyOCR downloads/
    initializes its detection+recognition models on first use, which is
    slow."""
    import easyocr

    return easyocr.Reader(list(langs), gpu=False)


def _script_char_count(text: str, script: str) -> int:
    lo, hi = _SCRIPT_RANGES[script]
    return sum(1 for c in text if lo <= ord(c) <= hi)


def _ocr_pdf_sync(path: str) -> str:
    """OCR fallback for a PDF whose text layer is garbled (see _is_garbled).
    Renders each page to an image with pypdfium2 (no poppler/system
    dependency) and reads the actually-rendered glyphs with EasyOCR - this
    sidesteps the broken text layer entirely, since OCR only cares what's
    visually drawn on the page, not what byte codes the PDF claims.

    CPU-only OCR is genuinely slow (measured ~70-240s/page depending on
    language), so running both readers (see _OCR_LANGUAGE_SETS) over every
    page - the simplest, most obviously-correct approach - is impractical
    for anything but a 1-2 page document: a real 14-page document measured
    out to over an hour. Instead, only one sample page (picked as whichever
    of the first three has the most text, to dodge a sparse cover page) is
    run through both readers to decide the script; every other page then
    uses only the winning reader, roughly halving total OCR time versus
    the double-pass and keeping it independent of document length.

    Runs synchronously in whatever process calls it - see _ocr_pdf (the
    public entry point) for why that must never be the main server
    process."""
    import numpy as np
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    page_images = [np.array(page.render(scale=200 / 72).to_pil()) for page in pdf]

    # A fixed "a few pages in" index, not page 0: cover/title pages are
    # often sparse on text, which would make a language guess off a single
    # near-blank page unreliable.
    sample_index = min(2, len(page_images) - 1)
    best_script, best_text, best_score = None, "", -1
    for script, langs in _OCR_LANGUAGE_SETS.items():
        reader = _ocr_reader(tuple(langs))
        text = "\n".join(reader.readtext(page_images[sample_index], detail=0, paragraph=True))
        score = _script_char_count(text, script)
        if score > best_score:
            best_score, best_script, best_text = score, script, text

    winning_reader = _ocr_reader(tuple(_OCR_LANGUAGE_SETS[best_script]))
    pages_text = [
        best_text if i == sample_index else "\n".join(winning_reader.readtext(img, detail=0, paragraph=True))
        for i, img in enumerate(page_images)
    ]
    return "\n\n".join(pages_text)


def _ocr_worker(path: str, conn) -> None:
    """Runs in a separate OS process (see _ocr_pdf)."""
    try:
        conn.send(("ok", _ocr_pdf_sync(path)))
    except Exception as exc:  # noqa: BLE001 - any failure must reach the parent as data, not a crash
        conn.send(("error", str(exc)))
    finally:
        conn.close()


def _ocr_pdf(path: str, timeout_seconds: int = 1800) -> str:
    """Runs _ocr_pdf_sync in an isolated child process rather than
    in-process, and is what every real caller should use.

    Confirmed by direct measurement: running EasyOCR's CPU inference
    in-process froze the ENTIRE FastAPI server - including trivially-fast
    endpoints like /health that touch no DB or auth - for over 10 minutes
    during a single ingestion. FastAPI's threadpool for sync handlers
    doesn't save this: CPU-bound numpy/torch inference holds the GIL for
    long stretches, starving every other thread in the same process
    (logins, unrelated requests, everything). A separate process has its
    own GIL and can't do this to the parent - the same reason
    diagram_execution.py isolates matplotlib rendering the same way."""
    import multiprocessing

    parent_conn, child_conn = multiprocessing.Pipe()
    process = multiprocessing.Process(target=_ocr_worker, args=(path, child_conn))
    process.start()

    if not parent_conn.poll(timeout_seconds):
        process.terminate()
        process.join()
        raise TimeoutError(f"OCR exceeded {timeout_seconds}s")

    status, payload = parent_conn.recv()
    process.join(timeout=5)
    if process.is_alive():
        process.terminate()
        process.join()

    if status == "error":
        raise RuntimeError(f"OCR failed: {payload}")
    return payload


def extract_text_from_pdf(path: str) -> str:
    """Extract text page by page using pdfplumber, falling back to pypdf on
    failure, then to OCR if the extracted text looks like a garbled legacy
    Indic font (see _is_garbled)."""
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(pages)
    except Exception:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)

    if _is_garbled(text):
        return _ocr_pdf(path)
    return text


def extract_text_from_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_from_pptx(path: str) -> str:
    """Extract slide title/body text and speaker notes, in slide order."""
    prs = Presentation(path)
    slides_text: list[str] = []

    for slide in prs.slides:
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            elif shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Notes: {notes}")
        slides_text.append("\n".join(parts))

    return "\n\n".join(s for s in slides_text if s)


def extract_text(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".pptx":
        return extract_text_from_pptx(path)
    if suffix == ".txt":
        return Path(path).read_text(encoding="utf-8")
    if suffix == ".ppt":
        raise ValueError(
            "Legacy .ppt is not directly supported — convert to .pptx first "
            "(e.g. open and Save As in PowerPoint)."
        )
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_text(
    text: str,
    source_document: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[TextChunk]:
    """Split text into overlapping word-based chunks for embedding/retrieval."""
    words = text.split()
    if not words:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    step = max(chunk_size - overlap, 1)

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(
            TextChunk(
                text=" ".join(chunk_words),
                chunk_index=index,
                source_document=source_document,
            )
        )
        index += 1
        start += step

    return chunks


def extract_and_chunk(path: str, chunk_size: int = 800, overlap: int = 150, text: str | None = None) -> list[TextChunk]:
    """Small overlapping chunks, sized for embedding/RAG retrieval (Phase 3).

    `text`, when given, skips re-extraction - pass in the result of an
    earlier extract_text(path) call. Ingestion needs both this and
    extract_and_chunk_for_extraction over the same file; extraction is the
    expensive part for a garbled-text-layer PDF that falls back to OCR
    (see _is_garbled/_ocr_pdf) - measured well over 15 minutes for a real
    14-page document - so a caller doing both must extract once and pass
    the text to both, not call extract_text twice."""
    if text is None:
        text = extract_text(path)
    return chunk_text(text, source_document=Path(path).name, chunk_size=chunk_size, overlap=overlap)


def extract_and_chunk_for_extraction(
    path: str, chunk_size: int = 4000, overlap: int = 0, text: str | None = None
) -> list[TextChunk]:
    """Large, mostly non-overlapping chunks for LLM graph extraction (Phase 2.2).

    Bigger chunks mean fewer LLM calls per document and let the model see
    relationships that span what would otherwise be separate retrieval
    chunks. `text`: see extract_and_chunk's docstring - same reasoning.
    """
    if text is None:
        text = extract_text(path)
    return chunk_text(text, source_document=Path(path).name, chunk_size=chunk_size, overlap=overlap)
