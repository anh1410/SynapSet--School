from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.academic import academic_year_for, check_academic_year, check_term


def mcq(text="Which of these is a mammal?", **over):
    base = {
        "text": text,
        "question_type": "mcq",
        "marks": 2,
        "difficulty": "easy",
        "options": ["Frog", "Whale", "Shark"],
        "correct_answer": "Whale",
    }
    return {**base, **over}


@pytest.fixture
def school(api_client, make_teacher):
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    return api_client, teacher, teacher_id, api_client.subject_id


def submit(teacher, sid, question):
    r = teacher.post("/api/v1/submissions", json={"subject_id": sid, "question": question})
    assert r.status_code == 200, r.text
    return r.json()


def bank(admin, sid):
    return admin.get("/api/v1/questions", params={"subject_id": sid}).json()


def log(admin, **params):
    r = admin.get("/api/v1/admin/audit", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- school year & term ----------


@pytest.mark.parametrize(
    "when,expected",
    [
        (datetime(2026, 6, 1, tzinfo=UTC), "2026-27"),
        (datetime(2026, 10, 4, tzinfo=UTC), "2026-27"),
        (datetime(2027, 3, 31, tzinfo=UTC), "2026-27"),
        (datetime(2027, 5, 31, tzinfo=UTC), "2026-27"),
        (datetime(2027, 6, 1, tzinfo=UTC), "2027-28"),
        (datetime(2099, 8, 1, tzinfo=UTC), "2099-00"),  # century rollover keeps two digits
    ],
)
def test_school_year_runs_june_to_may(when, expected):
    assert academic_year_for(when) == expected


def test_term_and_year_validation():
    assert check_term(None) is None and check_term("  ") is None
    assert check_term("Term 2") == "Term 2"
    with pytest.raises(ValueError):
        check_term("Whenever")
    assert check_academic_year("2026-27") == "2026-27"
    for bad in ("2026", "2026-28", "26-27", "2026/27", "abcd-ef"):
        with pytest.raises(ValueError):
            check_academic_year(bad)


def test_submitted_question_gets_the_current_year_and_optional_term(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq(term="Term 2"))
    q = sub["question"]
    assert q["term"] == "Term 2"
    assert q["academic_year"] == academic_year_for(datetime.now(UTC))
    assert submit(teacher, sid, mcq("No term here?"))["question"]["term"] is None


def test_teacher_cannot_choose_the_year_or_an_invalid_term(school):
    admin, teacher, _, sid = school
    forged = submit(teacher, sid, mcq(academic_year="1999-00"))
    assert forged["question"]["academic_year"] == academic_year_for(datetime.now(UTC))
    r = teacher.post("/api/v1/submissions", json={"subject_id": sid, "question": mcq(term="Whenever")})
    assert r.status_code == 422


def test_tags_survive_acceptance_into_the_bank(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq(term="Annual"))
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    banked = next(q for q in bank(admin, sid) if q["id"] == sub["question"]["id"])
    assert banked["term"] == "Annual"
    assert banked["academic_year"] == sub["question"]["academic_year"]


def make_paper(admin, sid, **extra):
    r = admin.post(
        "/api/v1/paper/blueprints",
        json={"subject_id": sid, "name": "Exam", "total_marks": 10, "sections": [], **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_paper_defaults_to_the_current_year_and_takes_a_term(school):
    admin, _, _, sid = school
    paper = make_paper(admin, sid)
    assert paper["academic_year"] == academic_year_for(datetime.now(UTC))
    assert paper["term"] is None

    tagged = make_paper(admin, sid, academic_year="2025-26", term="Term 1")
    assert (tagged["academic_year"], tagged["term"]) == ("2025-26", "Term 1")


def test_paper_year_and_term_can_be_changed_and_the_term_cleared(school):
    admin, _, _, sid = school
    paper = make_paper(admin, sid, term="Term 1")
    r = admin.patch(f"/api/v1/paper/blueprints/{paper['id']}", json={"academic_year": "2025-26", "term": "Annual"})
    assert (r.json()["academic_year"], r.json()["term"]) == ("2025-26", "Annual")

    r = admin.patch(f"/api/v1/paper/blueprints/{paper['id']}", json={"term": ""})
    assert r.json()["term"] is None
    assert r.json()["academic_year"] == "2025-26"

    r = admin.patch(f"/api/v1/paper/blueprints/{paper['id']}", json={"academic_year": ""})
    assert r.json()["academic_year"] == "2025-26"  # a paper always keeps a year


def test_invalid_paper_tags_are_rejected(school):
    admin, _, _, sid = school
    paper = make_paper(admin, sid)
    assert admin.patch(f"/api/v1/paper/blueprints/{paper['id']}", json={"term": "Whenever"}).status_code == 422
    assert admin.patch(f"/api/v1/paper/blueprints/{paper['id']}", json={"academic_year": "2026-99"}).status_code == 422
    r = admin.post("/api/v1/paper/blueprints", json={"subject_id": sid, "name": "x", "total_marks": 1, "term": "Bad"})
    assert r.status_code == 422


# ---------- admin edits a waiting submission ----------


def test_admin_fixes_a_waiting_submission(school):
    admin, teacher, teacher_id, sid = school
    sub = submit(teacher, sid, mcq("Which of these is a mamal?"))
    r = admin.patch(
        f"/api/v1/submissions/{sub['id']}/question",
        json={"question": mcq("Which of these is a mammal?", term="Term 1")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    q = body["question"]
    assert q["text"] == "Which of these is a mammal?"
    assert q["term"] == "Term 1"
    assert q["id"] == sub["question"]["id"]  # same question, so credits and history still line up
    assert q["author_id"] == teacher_id  # still credited to the teacher
    assert q["academic_year"] == sub["question"]["academic_year"]
    assert body["status"] == "submitted"
    assert [e["kind"] for e in body["history"]] == ["submitted", "edited"]
    assert body["history"][-1]["by_name"] == "Test Teacher"

    # the teacher sees the fix in their own list, and it can now be accepted as edited
    mine = teacher.get("/api/v1/submissions").json()[0]
    assert mine["question"]["text"] == "Which of these is a mammal?"
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    assert any(x["text"] == "Which of these is a mammal?" for x in bank(admin, sid))


def test_admin_edit_is_checked_like_any_submission(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq())
    r = admin.patch(
        f"/api/v1/submissions/{sub['id']}/question",
        json={"question": mcq(options=["Frog", "Whale"], correct_answer="Dolphin")},
    )
    assert r.status_code == 422


def test_only_waiting_submissions_can_be_edited_by_the_admin(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq())
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "reject"})
    r = admin.patch(f"/api/v1/submissions/{sub['id']}/question", json={"question": mcq("Changed?")})
    assert r.status_code == 409
    assert admin.patch("/api/v1/submissions/nope/question", json={"question": mcq()}).status_code == 404


def test_a_teacher_cannot_use_the_admin_edit(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq())
    assert teacher.patch(f"/api/v1/submissions/{sub['id']}/question", json={"question": mcq("Sneaky?")}).status_code == 403


# ---------- activity log ----------


def test_activity_log_records_who_did_what(school):
    admin, teacher, teacher_id, sid = school
    sub = submit(teacher, sid, mcq("Log me?"))
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept", "comment": "ok"})
    qid = sub["question"]["id"]
    paper = make_paper(admin, sid)
    admin.get(f"/api/v1/paper/blueprints/{paper['id']}/export", params={"format": "docx"})
    admin.delete(f"/api/v1/questions/{qid}")
    admin.delete(f"/api/v1/paper/blueprints/{paper['id']}")

    entries = log(admin)["items"]
    actions = [e["action"] for e in entries]
    for expected in (
        "teacher.create", "submission.accept", "paper.create", "paper.export", "question.delete", "paper.delete"
    ):
        assert expected in actions, expected
    assert actions.index("paper.delete") < actions.index("paper.create")  # newest first

    deleted = next(e for e in entries if e["action"] == "question.delete")
    assert deleted["actor_name"] == "Test Teacher"
    assert "Log me?" in deleted["summary"]
    assert deleted["target_id"] == qid
    accepted = next(e for e in entries if e["action"] == "submission.accept")
    assert "Ms. Iyer" in accepted["summary"]


def test_activity_log_covers_teacher_and_subject_changes(api_client, make_teacher):
    sid = api_client.subject_id
    teacher, teacher_id = make_teacher(subject_ids=[])
    api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"active": False})
    api_client.put(f"/api/v1/admin/teachers/{teacher_id}/subjects", json={"subject_ids": [sid]})
    other = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "6"}).json()
    api_client.patch(f"/api/v1/subjects/{other['id']}", json={"name": "Mathematics"})
    api_client.delete(f"/api/v1/subjects/{other['id']}")

    actions = {e["action"] for e in log(api_client)["items"]}
    assert {"teacher.update", "teacher.subjects", "subject.create", "subject.update", "subject.delete"} <= actions
    # a password reset is noted, but never the password itself
    api_client.patch(f"/api/v1/admin/teachers/{teacher_id}", json={"password": "brandnewpass1"})
    text = str(log(api_client))
    assert "password reset" in text and "brandnewpass1" not in text


def test_activity_log_filters(school):
    admin, teacher, teacher_id, sid = school
    sub = submit(teacher, sid, mcq("Findable question?"))
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "reject"})
    make_paper(admin, sid)

    assert {e["action"] for e in log(admin, area="paper")["items"]} == {"paper.create"}
    assert [e["action"] for e in log(admin, action="submission.reject")["items"]] == ["submission.reject"]
    hits = log(admin, q="Findable")["items"]
    assert hits and all("Findable" in e["summary"] for e in hits)
    me = admin.get("/api/v1/auth/me").json()["id"]
    assert all(e["actor_id"] == me for e in log(admin, actor_id=me)["items"])
    assert log(admin, actor_id="nobody")["items"] == []


def test_activity_log_pages_newest_first(school):
    admin, _, _, sid = school
    for i in range(5):
        make_paper(admin, sid)
    first = log(admin, limit=2)
    assert len(first["items"]) == 2 and first["has_more"] is True
    second = log(admin, limit=2, before=first["items"][-1]["at"])
    assert len(second["items"]) == 2
    assert {e["id"] for e in first["items"]}.isdisjoint(e["id"] for e in second["items"])
    assert log(admin, limit=500)["has_more"] is False


def test_only_admins_can_read_the_activity_log(school):
    admin, teacher, _, _ = school
    assert teacher.get("/api/v1/admin/audit").status_code == 403
    from app.main import app

    assert TestClient(app).get("/api/v1/admin/audit").status_code == 401


def test_a_failing_log_write_never_blocks_the_action(school, monkeypatch):
    admin, _, _, sid = school
    from app.core import audit_store

    def boom(self, entry):
        raise RuntimeError("disk full")

    monkeypatch.setattr(audit_store.AuditStore, "add", boom)
    assert admin.post(
        "/api/v1/paper/blueprints", json={"subject_id": sid, "name": "Still works", "total_marks": 1}
    ).status_code == 200
