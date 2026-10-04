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


def test_templates_are_scoped_to_the_admin_who_made_them(api_client, make_teacher):
    api_client.post("/api/v1/templates", json=_template_payload())

    # A second admin (a teacher promoted by the first) starts with no templates of their own.
    other_admin, other_id = make_teacher(email="second-admin@school.edu", name="Second Admin")
    api_client.patch(f"/api/v1/admin/teachers/{other_id}", json={"role": "admin"})

    assert other_admin.get("/api/v1/templates").json() == []


def test_teachers_cannot_use_templates(api_client, make_teacher):
    teacher, _ = make_teacher()
    assert teacher.get("/api/v1/templates").status_code == 403
    assert teacher.post("/api/v1/templates", json=_template_payload()).status_code == 403
