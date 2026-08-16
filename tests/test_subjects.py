from fastapi.testclient import TestClient


def test_list_subjects_includes_fixture_subject(api_client):
    r = api_client.get("/api/v1/subjects")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert api_client.subject_id in ids


def test_create_subject(api_client):
    r = api_client.post("/api/v1/subjects", json={"name": "Grade 8 Math"})
    assert r.status_code == 200
    assert r.json()["name"] == "Grade 8 Math"
    assert r.json()["teacher_id"]


def test_delete_subject(api_client):
    created = api_client.post("/api/v1/subjects", json={"name": "Temp Subject"}).json()
    r = api_client.delete(f"/api/v1/subjects/{created['id']}")
    assert r.status_code == 200

    ids = [s["id"] for s in api_client.get("/api/v1/subjects").json()]
    assert created["id"] not in ids


def test_delete_nonexistent_subject_is_404(api_client):
    r = api_client.delete("/api/v1/subjects/does-not-exist")
    assert r.status_code == 404


def test_another_teacher_cannot_see_or_touch_this_subject(api_client):
    from app.main import app

    other = TestClient(app)
    signup = other.post(
        "/api/v1/auth/signup",
        json={"email": "other-teacher@school.edu", "password": "otherpass123", "name": "Ms. Iyer"},
    )
    other.headers["Authorization"] = f"Bearer {signup.json()['access_token']}"

    # Other teacher's own subject list must not contain the fixture teacher's subject.
    ids = [s["id"] for s in other.get("/api/v1/subjects").json()]
    assert api_client.subject_id not in ids

    # Cross-teacher reads through subject-scoped endpoints 404, not 403 (no existence leak).
    r = other.get("/api/v1/graph", params={"subject_id": api_client.subject_id})
    assert r.status_code == 404

    r = other.delete(f"/api/v1/subjects/{api_client.subject_id}")
    assert r.status_code == 404
