from types import SimpleNamespace

from app.core.llm import _RATE_LIMIT_RETRY, embed_texts


def test_rate_limit_retry_budget_survives_a_full_rpm_window():
    # A short retry budget can give up before a per-minute rate-limit
    # window actually resets - this is a regression guard on the tuning,
    # not just its presence (see llm.py's _RATE_LIMIT_RETRY docstring).
    assert _RATE_LIMIT_RETRY["stop"].max_attempt_number >= 6
    assert _RATE_LIMIT_RETRY["wait"].max >= 60


def _fake_embed_response(batch: list[str]):
    # Deterministic fake vector per text so call order/content is checkable.
    return SimpleNamespace(embeddings=[SimpleNamespace(values=[float(len(t))]) for t in batch])


def test_embed_texts_empty_list_makes_no_call(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.core.llm.get_genai_client",
        lambda: SimpleNamespace(models=SimpleNamespace(embed_content=lambda **kw: calls.append(kw) or _fake_embed_response(kw["contents"]))),
    )
    assert embed_texts([]) == []
    assert calls == []


def test_embed_texts_single_batch_is_one_call(monkeypatch):
    calls = []

    def fake_embed_content(**kwargs):
        calls.append(kwargs["contents"])
        return _fake_embed_response(kwargs["contents"])

    monkeypatch.setattr(
        "app.core.llm.get_genai_client",
        lambda: SimpleNamespace(models=SimpleNamespace(embed_content=fake_embed_content)),
    )
    texts = ["a", "bb", "ccc"]
    result = embed_texts(texts)

    assert len(calls) == 1  # the whole point: one call, not one per text
    assert calls[0] == texts
    assert result == [[1.0], [2.0], [3.0]]  # order preserved


def test_embed_texts_splits_into_batches(monkeypatch):
    monkeypatch.setattr("app.core.llm.time.sleep", lambda _seconds: None)  # skip the real inter-batch pacing delay
    calls = []

    def fake_embed_content(**kwargs):
        calls.append(kwargs["contents"])
        return _fake_embed_response(kwargs["contents"])

    monkeypatch.setattr(
        "app.core.llm.get_genai_client",
        lambda: SimpleNamespace(models=SimpleNamespace(embed_content=fake_embed_content)),
    )
    texts = [str(i) for i in range(120)]  # > _EMBED_BATCH_SIZE (50)
    result = embed_texts(texts)

    assert len(calls) == 3  # 50 + 50 + 20
    assert sum(len(c) for c in calls) == 120
    assert len(result) == 120
