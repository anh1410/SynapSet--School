def _template_payload() -> dict:
    return {
        "name": "Unit Test Pattern",
        "duration_minutes": 45,
        "sections": [
            {"question_format": "fill_in_blank", "count": 2, "difficulty": "easy", "marks_per_question": 1},
            {"question_format": "short_answer", "count": 1, "difficulty": "medium", "marks_per_question": 3},
        ],
    }


def test_create_and_list_template(api_client):
    r = api_client.post("/api/v1/templates", json=_template_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Unit Test Pattern"
    assert len(body["sections"]) == 2
    assert body["teacher_id"]

    r = api_client.get("/api/v1/templates")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "Unit Test Pattern" in names


def test_delete_template(api_client):
    created = api_client.post("/api/v1/templates", json=_template_payload()).json()
    r = api_client.delete(f"/api/v1/templates/{created['id']}")
    assert r.status_code == 200

    ids = [t["id"] for t in api_client.get("/api/v1/templates").json()]
    assert created["id"] not in ids


def test_delete_nonexistent_template_is_404(api_client):
    r = api_client.delete("/api/v1/templates/does-not-exist")
    assert r.status_code == 404


def test_templates_are_teacher_scoped(api_client):
    from fastapi.testclient import TestClient

    from app.main import app

    api_client.post("/api/v1/templates", json=_template_payload())

    other = TestClient(app)
    signup = other.post(
        "/api/v1/auth/signup",
        json={"email": "other-template-teacher@school.edu", "password": "otherpass123", "name": "Mr. Rao"},
    )
    other.headers["Authorization"] = f"Bearer {signup.json()['access_token']}"

    assert other.get("/api/v1/templates").json() == []
