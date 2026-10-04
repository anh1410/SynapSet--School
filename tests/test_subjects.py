def test_list_subjects_includes_fixture_subject(api_client):
    r = api_client.get("/api/v1/subjects")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert api_client.subject_id in ids


def test_create_subject_with_grade(api_client):
    r = api_client.post("/api/v1/subjects", json={"name": "  Maths  ", "grade": "8"})
    assert r.status_code == 200
    assert r.json()["name"] == "Maths"  # trimmed
    assert r.json()["grade"] == "8"
    assert r.json()["teacher_id"]


def test_create_subject_accepts_lkg_and_ukg(api_client):
    for grade in ("LKG", "UKG"):
        r = api_client.post("/api/v1/subjects", json={"name": "EVS", "grade": grade})
        assert r.status_code == 200, r.text


def test_create_subject_rejects_unknown_grade(api_client):
    for bad in ("11", "0", "Grade 5", ""):
        r = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": bad})
        assert r.status_code == 422, bad


def test_create_subject_requires_grade_and_name(api_client):
    assert api_client.post("/api/v1/subjects", json={"name": "Maths"}).status_code == 422
    assert api_client.post("/api/v1/subjects", json={"name": "   ", "grade": "5"}).status_code == 422


def test_duplicate_subject_in_same_grade_rejected_but_other_grade_allowed(api_client):
    assert api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "6"}).status_code == 200
    assert api_client.post("/api/v1/subjects", json={"name": "maths", "grade": "6"}).status_code == 409
    assert api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "7"}).status_code == 200


def test_update_subject(api_client):
    r = api_client.patch(f"/api/v1/subjects/{api_client.subject_id}", json={"name": "Science", "grade": "9"})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["grade"]) == ("Science", "9")

    # partial update leaves the other field alone
    r = api_client.patch(f"/api/v1/subjects/{api_client.subject_id}", json={"grade": "10"})
    assert (r.json()["name"], r.json()["grade"]) == ("Science", "10")


def test_update_subject_cannot_collide_with_another(api_client):
    other = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "5"}).json()
    r = api_client.patch(f"/api/v1/subjects/{other['id']}", json={"name": "Test Subject"})
    assert r.status_code == 409


def test_update_nonexistent_subject_is_404(api_client):
    assert api_client.patch("/api/v1/subjects/nope", json={"name": "x"}).status_code == 404


def test_delete_subject(api_client):
    created = api_client.post("/api/v1/subjects", json={"name": "Temp Subject", "grade": "3"}).json()
    r = api_client.delete(f"/api/v1/subjects/{created['id']}")
    assert r.status_code == 200

    ids = [s["id"] for s in api_client.get("/api/v1/subjects").json()]
    assert created["id"] not in ids


def test_delete_subject_also_removes_teacher_assignments(api_client, make_teacher):
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    assert [s["id"] for s in teacher.get("/api/v1/subjects").json()] == [api_client.subject_id]

    api_client.delete(f"/api/v1/subjects/{api_client.subject_id}")

    assert teacher.get("/api/v1/subjects").json() == []
    listed = {t["id"]: t for t in api_client.get("/api/v1/admin/teachers").json()}
    assert listed[teacher_id]["subject_ids"] == []


def test_delete_nonexistent_subject_is_404(api_client):
    r = api_client.delete("/api/v1/subjects/does-not-exist")
    assert r.status_code == 404


def test_teacher_sees_only_assigned_subjects(api_client, make_teacher):
    other = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "5"}).json()
    teacher, _ = make_teacher(subject_ids=[other["id"]])

    ids = [s["id"] for s in teacher.get("/api/v1/subjects").json()]
    assert ids == [other["id"]]
    assert api_client.subject_id not in ids


def test_teacher_cannot_create_edit_or_delete_subjects(api_client, make_teacher):
    teacher, _ = make_teacher(subject_ids=[api_client.subject_id])

    assert teacher.post("/api/v1/subjects", json={"name": "Sneaky", "grade": "5"}).status_code == 403
    assert teacher.patch(f"/api/v1/subjects/{api_client.subject_id}", json={"name": "Renamed"}).status_code == 403
    assert teacher.delete(f"/api/v1/subjects/{api_client.subject_id}").status_code == 403

    # and nothing changed
    names = [s["name"] for s in api_client.get("/api/v1/subjects").json()]
    assert "Sneaky" not in names and "Renamed" not in names and "Test Subject" in names
