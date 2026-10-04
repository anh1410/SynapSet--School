import pytest
from fastapi.testclient import TestClient


def mcq(text="Which of these is a mammal?"):
    return {
        "text": text,
        "question_type": "mcq",
        "marks": 2,
        "difficulty": "easy",
        "options": ["Frog", "Whale", "Shark"],
        "correct_answer": "Whale",
    }


def accepted_question(admin, teacher, sid, text="Which of these is a mammal?") -> str:
    sub = teacher.post("/api/v1/submissions", json={"subject_id": sid, "question": mcq(text)}).json()
    r = admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    assert r.status_code == 200, r.text
    return sub["question"]["id"]


def make_paper(admin, sid, question_ids, name="Term 1 Exam") -> str:
    r = admin.post(
        "/api/v1/paper/blueprints",
        json={
            "subject_id": sid,
            "name": name,
            "total_marks": 10,
            "sections": [{"title": "A", "question_format": "mcq", "question_ids": question_ids}],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def export(admin, blueprint_id):
    r = admin.get(f"/api/v1/paper/blueprints/{blueprint_id}/export", params={"format": "docx"})
    assert r.status_code == 200, r.text


@pytest.fixture
def school(api_client, make_teacher):
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    return api_client, teacher, teacher_id, api_client.subject_id


def credits(client):
    r = client.get("/api/v1/credits")
    assert r.status_code == 200, r.text
    return r.json()


def test_no_credit_until_the_paper_is_exported(school):
    admin, teacher, _, sid = school
    qid = accepted_question(admin, teacher, sid)
    make_paper(admin, sid, [qid])
    assert credits(teacher) == {"total": 0, "items": []}


def test_export_credits_the_author_with_question_and_exam_name_only(school):
    admin, teacher, teacher_id, sid = school
    qid = accepted_question(admin, teacher, sid)
    other = admin.post("/api/v1/questions", json={
        "id": "admins-own", "subject_id": sid, "text": "Admin wrote this", "question_type": "short_answer", "marks": 1,
        "bloom_level": 2, "topic_ids": [], "co_ids": [], "correct_answer": "x",
    })
    assert other.status_code == 200, other.text
    paper = make_paper(admin, sid, [qid, "admins-own"], name="Annual Exam")
    export(admin, paper)

    body = credits(teacher)
    assert body["total"] == 1  # the admin's own question earns nobody anything
    item = body["items"][0]
    assert item["question_id"] == qid
    assert item["question_text"] == "Which of these is a mammal?"
    assert item["exam_name"] == "Annual Exam"
    assert item["subject_name"] == "Test Subject"
    # nothing about the paper's contents
    assert set(item) == {
        "id", "question_id", "question_text", "question_type", "marks", "exam_name",
        "subject_name", "subject_grade", "earned_at",
    }
    assert "admins-own" not in str(body) and "Admin wrote this" not in str(body)


def test_exporting_again_does_not_double_credit(school):
    admin, teacher, _, sid = school
    paper = make_paper(admin, sid, [accepted_question(admin, teacher, sid)])
    export(admin, paper)
    export(admin, paper)
    admin.get(f"/api/v1/paper/blueprints/{paper}/export", params={"format": "pdf", "variant": "answer_key"})
    assert credits(teacher)["total"] == 1


def test_same_question_in_two_papers_earns_two_credits(school):
    admin, teacher, _, sid = school
    qid = accepted_question(admin, teacher, sid)
    export(admin, make_paper(admin, sid, [qid], name="Unit Test"))
    export(admin, make_paper(admin, sid, [qid], name="Midterm"))
    names = sorted(i["exam_name"] for i in credits(teacher)["items"])
    assert names == ["Midterm", "Unit Test"]


def test_removing_a_question_and_reexporting_takes_its_credit_back(school):
    admin, teacher, _, sid = school
    q1 = accepted_question(admin, teacher, sid, "First question?")
    q2 = accepted_question(admin, teacher, sid, "Second question?")
    paper = make_paper(admin, sid, [q1, q2])
    export(admin, paper)
    assert credits(teacher)["total"] == 2

    admin.patch(
        f"/api/v1/paper/blueprints/{paper}",
        json={"sections": [{"title": "A", "question_format": "mcq", "question_ids": [q1]}]},
    )
    export(admin, paper)
    assert [i["question_id"] for i in credits(teacher)["items"]] == [q1]


def test_renaming_an_exported_paper_updates_the_exam_name(school):
    admin, teacher, _, sid = school
    paper = make_paper(admin, sid, [accepted_question(admin, teacher, sid)], name="Draft title")
    export(admin, paper)
    admin.patch(f"/api/v1/paper/blueprints/{paper}", json={"name": "Final title"})
    assert credits(teacher)["items"][0]["exam_name"] == "Final title"


def test_marking_a_paper_exported_or_back_to_draft(school):
    admin, teacher, _, sid = school
    paper = make_paper(admin, sid, [accepted_question(admin, teacher, sid)])
    admin.patch(f"/api/v1/paper/blueprints/{paper}", json={"status": "exported"})
    assert credits(teacher)["total"] == 1
    admin.patch(f"/api/v1/paper/blueprints/{paper}", json={"status": "draft"})
    assert credits(teacher)["total"] == 0


def test_credit_survives_deleting_the_paper_and_the_bank_question(school):
    admin, teacher, _, sid = school
    qid = accepted_question(admin, teacher, sid)
    paper = make_paper(admin, sid, [qid])
    export(admin, paper)
    admin.delete(f"/api/v1/questions/{qid}")
    admin.delete(f"/api/v1/paper/blueprints/{paper}")
    item = credits(teacher)["items"][0]
    assert item["question_text"] == "Which of these is a mammal?"
    assert item["exam_name"] == "Term 1 Exam"


def test_teachers_only_see_their_own_credits(api_client, make_teacher):
    sid = api_client.subject_id
    t1, _ = make_teacher(email="a@school.edu", name="Ms. A", subject_ids=[sid])
    t2, _ = make_teacher(email="b@school.edu", name="Mr. B", subject_ids=[sid])
    q1 = accepted_question(api_client, t1, sid, "A's question?")
    q2 = accepted_question(api_client, t2, sid, "B's question?")
    export(api_client, make_paper(api_client, sid, [q1, q2]))
    assert [i["question_text"] for i in credits(t1)["items"]] == ["A's question?"]
    assert [i["question_text"] for i in credits(t2)["items"]] == ["B's question?"]


def test_admin_sees_credit_counts_per_teacher(school):
    admin, teacher, teacher_id, sid = school
    q1 = accepted_question(admin, teacher, sid, "One?")
    q2 = accepted_question(admin, teacher, sid, "Two?")
    export(admin, make_paper(admin, sid, [q1, q2]))
    rows = {t["id"]: t for t in admin.get("/api/v1/admin/teachers").json()}
    assert rows[teacher_id]["credit_count"] == 2


def test_a_teacher_cannot_export_papers_or_peek_at_them(school):
    admin, teacher, _, sid = school
    paper = make_paper(admin, sid, [accepted_question(admin, teacher, sid)])
    assert teacher.get(f"/api/v1/paper/blueprints/{paper}/export").status_code == 403
    assert teacher.get(f"/api/v1/paper/blueprints/{paper}").status_code == 403
    assert credits(teacher)["total"] == 0


def test_credits_require_login(school):
    from app.main import app

    assert TestClient(app).get("/api/v1/credits").status_code == 401
