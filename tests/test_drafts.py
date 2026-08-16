def _draft_payload(subject_id: str) -> dict:
    return {
        "id": "draft-1",
        "teacher_id": "ignored-overwritten-by-server",
        "subject_id": subject_id,
        "paper_name": "My Draft Paper",
        "duration_minutes": 60,
        "sections": [
            {
                "id": "section-1",
                "question_format": "short_answer",
                "count": 3,
                "topic_ids": ["photosynthesis"],
                "difficulty": "medium",
                "marks_per_question": 3,
                "generated_question_ids": [],
            }
        ],
        "updated_at": "2026-01-01T00:00:00Z",
    }


def test_get_draft_when_none_exists_returns_null(api_client):
    r = api_client.get("/api/v1/drafts", params={"subject_id": api_client.subject_id})
    assert r.status_code == 200
    assert r.json() is None


def test_put_then_get_draft_round_trips(api_client):
    payload = _draft_payload(api_client.subject_id)
    r = api_client.put("/api/v1/drafts", json=payload)
    assert r.status_code == 200
    assert r.json()["paper_name"] == "My Draft Paper"

    r = api_client.get("/api/v1/drafts", params={"subject_id": api_client.subject_id})
    assert r.status_code == 200
    body = r.json()
    assert body["paper_name"] == "My Draft Paper"
    assert body["sections"][0]["difficulty"] == "medium"


def test_put_draft_overwrites_previous_draft_for_same_subject(api_client):
    api_client.put("/api/v1/drafts", json=_draft_payload(api_client.subject_id))
    second = _draft_payload(api_client.subject_id)
    second["id"] = "draft-2"
    second["paper_name"] = "Replacement Draft"
    api_client.put("/api/v1/drafts", json=second)

    r = api_client.get("/api/v1/drafts", params={"subject_id": api_client.subject_id})
    assert r.json()["paper_name"] == "Replacement Draft"
    assert r.json()["id"] == "draft-2"


def test_delete_draft_clears_it(api_client):
    api_client.put("/api/v1/drafts", json=_draft_payload(api_client.subject_id))
    r = api_client.delete("/api/v1/drafts", params={"subject_id": api_client.subject_id})
    assert r.status_code == 200
    assert r.json()["cleared"] is True

    r = api_client.get("/api/v1/drafts", params={"subject_id": api_client.subject_id})
    assert r.json() is None
