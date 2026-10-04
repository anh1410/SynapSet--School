import pytest


def _teachers(api_client):
    return {t["id"]: t for t in api_client.get("/api/v1/admin/teachers").json()}


# ---------- creating / listing teachers ----------


def test_admin_creates_teacher_who_can_log_in(api_client, make_teacher):
    teacher, teacher_id = make_teacher(email="ms.iyer@school.edu", name="Ms. Iyer")

    me = teacher.get("/api/v1/auth/me").json()
    assert me["email"] == "ms.iyer@school.edu"
    assert me["role"] == "teacher"
    assert "password_hash" not in me

    listed = _teachers(api_client)[teacher_id]
    assert listed["role"] == "teacher"
    assert listed["active"] is True
    assert listed["subject_ids"] == []
    assert "password_hash" not in listed


def test_create_teacher_with_subjects_assigned(api_client, make_teacher):
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    assert _teachers(api_client)[teacher_id]["subject_ids"] == [api_client.subject_id]
    assert [s["id"] for s in teacher.get("/api/v1/subjects").json()] == [api_client.subject_id]


def test_duplicate_email_rejected_case_insensitively(api_client, make_teacher):
    make_teacher(email="dup@school.edu")
    r = api_client.post(
        "/api/v1/admin/teachers", json={"name": "Dup", "email": "DUP@school.edu", "password": "longenough1"}
    )
    assert r.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A", "email": "a@school.edu", "password": "short"},  # password too short
        {"name": "A", "email": "not-an-email", "password": "longenough1"},
        {"name": "   ", "email": "a@school.edu", "password": "longenough1"},
    ],
)
def test_create_teacher_validation(api_client, payload):
    assert api_client.post("/api/v1/admin/teachers", json=payload).status_code == 422


def test_create_teacher_with_unknown_subject_fails_and_creates_nothing(api_client):
    r = api_client.post(
        "/api/v1/admin/teachers",
        json={"name": "A", "email": "a@school.edu", "password": "longenough1", "subject_ids": ["nope"]},
    )
    assert r.status_code == 400
    assert "a@school.edu" not in [t["email"] for t in _teachers(api_client).values()]


# ---------- assigning subjects ----------


def test_set_teacher_subjects_replaces_the_list(api_client, make_teacher):
    second = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "6"}).json()
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])

    r = api_client.put(f"/api/v1/admin/teachers/{teacher_id}/subjects", json={"subject_ids": [second["id"]]})
    assert r.status_code == 200
    assert r.json()["subject_ids"] == [second["id"]]
    assert [s["id"] for s in teacher.get("/api/v1/subjects").json()] == [second["id"]]

    cleared = api_client.put(f"/api/v1/admin/teachers/{teacher_id}/subjects", json={"subject_ids": []})
    assert cleared.json()["subject_ids"] == []
    assert teacher.get("/api/v1/subjects").json() == []


def test_set_teacher_subjects_dedupes(api_client, make_teacher):
    _, teacher_id = make_teacher()
    r = api_client.put(
        f"/api/v1/admin/teachers/{teacher_id}/subjects",
        json={"subject_ids": [api_client.subject_id, api_client.subject_id]},
    )
    assert r.status_code == 200
    assert r.json()["subject_ids"] == [api_client.subject_id]


def test_set_teacher_subjects_rejects_unknown_subject_and_changes_nothing(api_client, make_teacher):
    _, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    r = api_client.put(f"/api/v1/admin/teachers/{teacher_id}/subjects", json={"subject_ids": ["nope"]})
    assert r.status_code == 400
    assert _teachers(api_client)[teacher_id]["subject_ids"] == [api_client.subject_id]


def test_cannot_assign_subjects_to_an_admin(api_client):
    me = api_client.get("/api/v1/auth/me").json()
    r = api_client.put(f"/api/v1/admin/teachers/{me['id']}/subjects", json={"subject_ids": []})
    assert r.status_code == 400


def test_assign_unknown_teacher_is_404(api_client):
    assert api_client.put("/api/v1/admin/teachers/nope/subjects", json={"subject_ids": []}).status_code == 404


# ---------- permissions: teachers must be blocked server-side ----------


def test_teacher_blocked_from_admin_api_even_when_assigned_the_subject(api_client, make_teacher):
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    sid = api_client.subject_id

    forbidden_gets = [
        "/api/v1/admin/teachers",
        f"/api/v1/questions?subject_id={sid}",
        f"/api/v1/graph?subject_id={sid}",
        f"/api/v1/graph/documents?subject_id={sid}",
        f"/api/v1/paper/blueprints?subject_id={sid}",
        f"/api/v1/drafts?subject_id={sid}",
        "/api/v1/templates",
    ]
    for url in forbidden_gets:
        assert teacher.get(url).status_code == 403, url

    # The generation / upload / paper-building entry points specifically.
    assert (
        teacher.post(
            "/api/v1/questions/generate", json={"subject_id": sid, "topic": "x", "num_questions": 1}
        ).status_code
        == 403
    )
    assert (
        teacher.post(
            "/api/v1/graph/ingest",
            data={"subject_id": sid, "category": "notes"},
            files={"file": ("a.txt", b"hello", "text/plain")},
        ).status_code
        == 403
    )
    assert teacher.post("/api/v1/paper/optimize", json={"subject_id": sid, "constraints": {}}).status_code == 403
    assert teacher.post("/api/v1/admin/teachers", json={}).status_code == 403
    assert teacher.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"role": "admin"}).status_code == 403
    assert teacher.delete(f"/api/v1/admin/teachers/{teacher_id}").status_code == 403


def test_teacher_cannot_promote_themselves(api_client, make_teacher):
    teacher, teacher_id = make_teacher()
    teacher.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"role": "admin"})
    assert teacher.get("/api/v1/auth/me").json()["role"] == "teacher"
    assert _teachers(api_client)[teacher_id]["role"] == "teacher"


def test_teacher_can_still_load_images_endpoint_auth(make_teacher):
    # Images are served to any logged-in account (needed to show a teacher
    # their own diagram questions later); a missing id is a 404, not a 403.
    teacher, _ = make_teacher()
    assert teacher.get("/api/v1/images/does-not-exist").status_code == 404


# ---------- editing / deactivating / deleting ----------


def test_promote_teacher_to_admin_grants_admin_access(api_client, make_teacher):
    teacher, teacher_id = make_teacher()
    assert teacher.get("/api/v1/admin/teachers").status_code == 403

    r = api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    assert teacher.get("/api/v1/admin/teachers").status_code == 200
    # an admin sees every subject, not just assigned ones
    assert api_client.subject_id in [s["id"] for s in teacher.get("/api/v1/subjects").json()]


def test_deactivated_teacher_cannot_log_in_or_use_existing_token(api_client, make_teacher):
    teacher, teacher_id = make_teacher(email="leaving@school.edu")
    assert teacher.get("/api/v1/auth/me").status_code == 200

    r = api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False

    assert teacher.get("/api/v1/auth/me").status_code == 403  # token that was already issued
    from app.main import app
    from fastapi.testclient import TestClient

    login = TestClient(app).post("/api/v1/auth/login", json={"email": "leaving@school.edu", "password": "teacherpass1"})
    assert login.status_code == 403
    assert "deactivated" in login.json()["detail"].lower()

    api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"active": True})
    assert teacher.get("/api/v1/auth/me").status_code == 200


def test_admin_can_reset_a_teachers_password(api_client, make_teacher):
    from app.main import app
    from fastapi.testclient import TestClient

    _, teacher_id = make_teacher(email="forgot@school.edu")
    assert api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"password": "short"}).status_code == 422

    assert api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"password": "brandnewpass1"}).status_code == 200

    fresh = TestClient(app)
    assert fresh.post("/api/v1/auth/login", json={"email": "forgot@school.edu", "password": "teacherpass1"}).status_code == 401
    assert fresh.post("/api/v1/auth/login", json={"email": "forgot@school.edu", "password": "brandnewpass1"}).status_code == 200


def test_admin_can_rename_a_teacher(api_client, make_teacher):
    _, teacher_id = make_teacher(name="Old Name")
    r = api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"name": "New Name"})
    assert r.json()["name"] == "New Name"
    assert api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"name": "  "}).status_code == 422


def test_admin_cannot_demote_deactivate_or_delete_themselves(api_client):
    me = api_client.get("/api/v1/auth/me").json()

    assert api_client.patch(f"/api/v1/admin/teachers/{me['id']}", json={"role": "teacher"}).status_code == 400
    assert api_client.patch(f"/api/v1/admin/teachers/{me['id']}", json={"active": False}).status_code == 400
    assert api_client.delete(f"/api/v1/admin/teachers/{me['id']}").status_code == 400

    # still an active admin
    assert api_client.get("/api/v1/auth/me").json()["role"] == "admin"
    # but renaming themselves is fine
    assert api_client.patch(f"/api/v1/admin/teachers/{me['id']}", json={"name": "Renamed Admin"}).status_code == 200


def test_delete_teacher_removes_account_and_assignments(api_client, make_teacher):
    from app.main import app
    from fastapi.testclient import TestClient

    _, teacher_id = make_teacher(email="gone@school.edu", subject_ids=[api_client.subject_id])
    assert api_client.delete(f"/api/v1/admin/teachers/{teacher_id}").status_code == 200

    assert teacher_id not in _teachers(api_client)
    assert TestClient(app).post(
        "/api/v1/auth/login", json={"email": "gone@school.edu", "password": "teacherpass1"}
    ).status_code == 401
    # the subject itself is school-wide and survives
    assert api_client.subject_id in [s["id"] for s in api_client.get("/api/v1/subjects").json()]


def test_edit_or_delete_unknown_teacher_is_404(api_client):
    assert api_client.patch("/api/v1/admin/teachers/nope", json={"name": "x"}).status_code == 404
    assert api_client.delete("/api/v1/admin/teachers/nope").status_code == 404


# ---------- upgrading a database that predates roles ----------


def _legacy_setup(api_client):
    """Simulates a pre-roles database: nobody is an admin, and subjects are owned by
    individual accounts. Returns (stores..., first_account)."""
    from app.core.subject_store import get_subject_store
    from app.core.teacher_store import get_teacher_store

    teachers, subjects = get_teacher_store(), get_subject_store()
    first = teachers.list()[0]  # the api_client's account, owns 1 subject
    teachers.add(first.model_copy(update={"role": "teacher"}))
    return teachers, subjects, first


def test_bootstrap_promotes_owner_of_most_subjects_and_preserves_access(api_client):
    from app.core.bootstrap import ensure_admin_exists
    from app.schemas.subject import Subject
    from app.schemas.teacher import Teacher

    teachers, subjects, first = _legacy_setup(api_client)
    busy = Teacher(id="busy", email="busy@school.edu", name="Busy", password_hash="x")
    teachers.add(busy)
    for i in range(2):
        subjects.add(Subject(id=f"s{i}", teacher_id="busy", name=f"S{i}", grade="5"))

    ensure_admin_exists()

    assert teachers.get("busy").role == "admin"  # owns 2 subjects vs the first account's 1
    assert teachers.get(first.id).role == "teacher"
    # the old owner keeps their subject; the new admin needs no assignment
    assert subjects.is_assigned(first.id, api_client.subject_id)
    assert not subjects.is_assigned("busy", "s0")


def test_bootstrap_tie_goes_to_the_earliest_account(api_client):
    from app.core.bootstrap import ensure_admin_exists
    from app.schemas.subject import Subject
    from app.schemas.teacher import Teacher

    teachers, subjects, first = _legacy_setup(api_client)
    later = Teacher(id="later", email="later@school.edu", name="Later", password_hash="x")
    teachers.add(later)
    subjects.add(Subject(id="s0", teacher_id="later", name="S0", grade="5"))  # 1 each

    ensure_admin_exists()

    assert teachers.get(first.id).role == "admin"
    assert teachers.get("later").role == "teacher"


def test_bootstrap_never_re_adds_an_assignment_an_admin_removed(api_client):
    from app.core.bootstrap import ensure_admin_exists
    from app.schemas.subject import Subject
    from app.schemas.teacher import Teacher

    teachers, subjects, first = _legacy_setup(api_client)
    teachers.add(Teacher(id="busy", email="busy@school.edu", name="Busy", password_hash="x"))
    for i in range(2):
        subjects.add(Subject(id=f"s{i}", teacher_id="busy", name=f"S{i}", grade="5"))
    ensure_admin_exists()
    assert subjects.is_assigned(first.id, api_client.subject_id)

    subjects.set_teacher_subjects(first.id, [])  # admin deliberately unassigns
    ensure_admin_exists()  # e.g. the next server restart

    assert not subjects.is_assigned(first.id, api_client.subject_id)


def test_bootstrap_does_nothing_when_an_admin_exists(api_client):
    from app.core.bootstrap import ensure_admin_exists
    from app.core.teacher_store import get_teacher_store

    before = {t.id: t.role for t in get_teacher_store().list()}
    ensure_admin_exists()
    assert {t.id: t.role for t in get_teacher_store().list()} == before


def test_bootstrap_does_nothing_with_no_accounts(empty_client):
    from app.core.bootstrap import ensure_admin_exists
    from app.core.teacher_store import get_teacher_store

    ensure_admin_exists()
    assert get_teacher_store().list() == []
