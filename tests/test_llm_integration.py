"""Tests that hit the real Gemini API. Excluded from the default run (see pyproject.toml).
Run explicitly with: pytest -m llm
"""

import pytest

from app.core.graph_store import KnowledgeGraphStore
from app.core.llm import embed_texts
from app.schemas.bloom import BloomLevel
from app.schemas.question import QuestionType
from app.services.document_extraction import TextChunk
from app.services.entity_extraction import extract_from_chunk
from app.services.image_generation import generate_image
from app.services.question_generation import generate_questions

pytestmark = pytest.mark.llm


def test_extract_from_chunk_real():
    chunk = TextChunk(
        text=(
            "Virtualization is the process of creating a virtual version of a physical resource. "
            "A hypervisor manages virtual machines. Virtualization is a prerequisite for "
            "Infrastructure as a Service (IaaS)."
        ),
        chunk_index=0,
        source_document="test.txt",
    )
    result = extract_from_chunk(chunk)
    assert len(result.topics) > 0


def test_embed_texts_batches_real_ingestion_size():
    """Simulates the chunk count a ~20-page document actually produces
    (document_extraction.py's retrieval chunking) to prove batching avoids
    the burst-of-many-calls pattern that triggered a real 429
    RESOURCE_EXHAUSTED during ingestion."""
    texts = [f"Chunk {i} discusses a different topic each time to keep embeddings distinct." for i in range(16)]
    embeddings = embed_texts(texts)
    assert len(embeddings) == 16
    assert all(len(e) > 0 for e in embeddings)


def test_generate_questions_real(tmp_path):
    gs = KnowledgeGraphStore(str(tmp_path / "g.gpickle"))
    gs.add_topic("virtualization", name="Virtualization", importance_score=0.5)

    questions = generate_questions(
        topic="Virtualization",
        graph_store=gs,
        subject_id="sub1",
        num_questions=1,
        bloom_level=BloomLevel.UNDERSTAND,
        marks=5,
        question_type=QuestionType.SHORT_ANSWER,
    )
    assert len(questions) >= 1
    assert questions[0].text


def test_generate_image_real():
    """Needs a Gemini API key with billing enabled - the free tier has a
    zero quota for image-generation models (see image_generation.py)."""
    png = generate_image("minimalist colorful vector illustration of a frog, white background")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
