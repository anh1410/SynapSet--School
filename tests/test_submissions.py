import pytest
from fastapi.testclient import TestClient


# ---------- payload builders ----------


def mcq(**over):
    base = {
        "text": "Which of these is a mammal?",
        "question_type": "mcq",
        "marks": 2,
        "bloom_level": 1,
        "options": ["Frog", "Whale", "Shark"],
        "correct_answer": "Whale",
    }
    return {**base, **over}


def short(**over):
    base = {"text": "Define photosynthesis.", "question_type": "short_answer", "marks": 3, "correct_answer": "Plants make food using light."}
    return {**base, **over}


def submit(client, subject_id, question):
    return client.post("/api/v1/submissions", json={"subject_id": subject_id, "question": question})


@pytest.fixture
def school(api_client, make_teacher):
    """An admin (api_client), one subject, and a teacher assigned to it."""
    teacher, teacher_id = make_teacher(subject_ids=[api_client.subject_id])
    return api_client, teacher, teacher_id, api_client.subject_id


# ---------- creating ----------


def test_teacher_submits_a_question(school):
    admin, teacher, teacher_id, sid = school
    r = submit(teacher, sid, mcq())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "submitted"
    assert body["teacher_id"] == teacher_id
    assert body["subject_id"] == sid
    assert body["subject_name"] == "Test Subject"
    assert body["subject_grade"] == "5"
    assert body["question"]["author_id"] == teacher_id
    assert body["question"]["id"]
    assert body["history"][0]["kind"] == "submitted"
    assert body["duplicate_hits"] == []  # teachers never see other questions


def test_teacher_cannot_submit_to_a_subject_they_are_not_assigned(api_client, make_teacher):
    other = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "6"}).json()
    teacher, _ = make_teacher(subject_ids=[api_client.subject_id])
    assert submit(teacher, other["id"], mcq()).status_code == 404
    assert submit(teacher, "no-such-subject", mcq()).status_code == 404


def test_teacher_cannot_forge_authorship_or_scores(school):
    admin, teacher, teacher_id, sid = school
    forged = mcq(author_id="someone-else", id="my-own-id", difficulty_score=9.9, is_duplicate_of="x", source_document="exam.pdf")
    body = submit(teacher, sid, forged).json()
    assert body["question"]["author_id"] == teacher_id
    assert body["question"]["id"] != "my-own-id"
    assert body["question"]["difficulty_score"] is None
    assert body["question"]["is_duplicate_of"] is None
    assert body["question"]["source_document"] is None


@pytest.mark.parametrize(
    "level,bloom,score",
    [("easy", 1, 2.5), ("medium", 3, 5.5), ("hard", 4, 8.5)],
)
def test_teacher_picks_easy_medium_or_hard(school, level, bloom, score):
    admin, teacher, _, sid = school
    q = submit(teacher, sid, mcq(difficulty=level, bloom_level=6)).json()["question"]  # bloom_level is ignored
    assert q["bloom_level"] == bloom
    assert q["difficulty_score"] == score


def test_unknown_difficulty_is_rejected(school):
    admin, teacher, _, sid = school
    assert submit(teacher, sid, mcq(difficulty="impossible")).status_code == 422


def test_accepting_keeps_the_teachers_difficulty(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq(difficulty="hard")).json()
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    banked = next(q for q in admin.get("/api/v1/questions", params={"subject_id": sid}).json() if q["id"] == sub["question"]["id"])
    assert banked["difficulty_score"] == 8.5


def test_unauthenticated_cannot_submit(school):
    from app.main import app

    _, _, _, sid = school
    assert submit(TestClient(app), sid, mcq()).status_code == 401


@pytest.mark.parametrize(
    "question, fragment",
    [
        (mcq(text="   "), "write the question"),
        (mcq(marks=0), "marks"),
        (mcq(marks=101), "marks"),
        (mcq(options=["Only one"], correct_answer="Only one"), "options"),
        (mcq(options=["A", "B", "C", "D", "E", "F", "G", "H", "I"], correct_answer="A"), "options"),
        (mcq(options=["Frog", "", "Shark"]), "every option"),
        (mcq(options=["Frog", "frog", "Shark"], correct_answer="Frog"), "same"),
        (mcq(correct_answer="Dolphin"), "correct answer"),
        (mcq(correct_answer=None), "correct answer"),
        (short(correct_answer="  "), "answer"),
        (short(correct_answer=None), "answer"),
        ({**short(), "question_type": "fill_in_blank", "text": "The sky is blue.", "correct_answer": "blue"}, "blank"),
        ({"text": "Match them", "question_type": "match_following", "marks": 4, "match_pairs": [{"left": "a", "right": "b"}]}, "pairs"),
        ({"text": "Match them", "question_type": "match_following", "marks": 4, "match_pairs": [{"left": "a", "right": "b"}, {"left": "c", "right": ""}]}, "both sides"),
        ({"text": "Earth is flat", "question_type": "true_false", "marks": 1}, "true or false"),
        (short(topic_ids=["not-a-real-topic"]), "topic"),
        (short(diagram={"image_id": "0" * 32}), "couldn't be found"),
        (short(diagram={"image_id": "../../etc/passwd"}), "couldn't be found"),
    ],
)
def test_invalid_submissions_are_rejected_with_a_helpful_message(school, question, fragment):
    _, teacher, _, sid = school
    r = submit(teacher, sid, question)
    assert r.status_code == 422, r.text
    assert fragment in str(r.json()["detail"]).lower()


def test_unknown_question_type_is_rejected(school):
    _, teacher, _, sid = school
    assert submit(teacher, sid, short(question_type="essay")).status_code == 422


def test_fields_that_dont_belong_to_the_type_are_dropped(school):
    _, teacher, _, sid = school
    q = submit(teacher, sid, short(options=["x", "y"], match_pairs=[{"left": "a", "right": "b"}], is_true=True)).json()["question"]
    assert q["options"] is None and q["match_pairs"] is None and q["is_true"] is None


def test_text_is_trimmed_and_options_trimmed(school):
    _, teacher, _, sid = school
    q = submit(teacher, sid, mcq(text="  Which?  ", options=["  Frog ", " Whale", "Shark  "], correct_answer=" Whale ")).json()["question"]
    assert q["text"] == "Which?"
    assert q["options"] == ["Frog", "Whale", "Shark"]
    assert q["correct_answer"] == "Whale"


def test_every_text_type_can_be_submitted(school):
    _, teacher, _, sid = school
    cases = [
        mcq(),
        short(),
        {**short(), "question_type": "long_answer", "marks": 7},
        {**short(), "question_type": "numerical", "correct_answer": "42 cm"},
        {**short(), "question_type": "fill_in_blank", "text": "The capital of India is _____.", "correct_answer": "New Delhi"},
        {**short(), "question_type": "stem_diagram", "text": "Solve $x^2 = 4$.", "correct_answer": "$x = \\pm 2$"},
        {"text": "Match the following", "question_type": "match_following", "marks": 4, "match_pairs": [{"left": "Sun", "right": "Star"}, {"left": "Moon", "right": "Satellite"}]},
        {"text": "The Earth is round.", "question_type": "true_false", "marks": 1, "is_true": True},
        {"text": "The Earth is flat.", "question_type": "true_false", "marks": 1, "is_true": False},
    ]
    for case in cases:
        r = submit(teacher, sid, case)
        assert r.status_code == 200, (case["question_type"], r.text)


def test_hindi_and_kannada_questions_are_accepted(school):
    _, teacher, _, sid = school
    r = submit(teacher, sid, mcq(text="ಕರ್ನಾಟಕದ ರಾಜಧಾನಿ ಯಾವುದು?", options=["ಮೈಸೂರು", "ಬೆಂಗಳೂರು"], correct_answer="ಬೆಂಗಳೂರು"))
    assert r.status_code == 200
    assert r.json()["question"]["correct_answer"] == "ಬೆಂಗಳೂರು"


def test_match_question_gets_a_shuffled_column_b_order(school):
    _, teacher, _, sid = school
    pairs = [{"left": str(i), "right": str(i)} for i in range(5)]
    q = submit(teacher, sid, {"text": "Match", "question_type": "match_following", "marks": 5, "match_pairs": pairs}).json()["question"]
    assert sorted(q["match_right_order"]) == [0, 1, 2, 3, 4]


def test_topics_can_be_attached(school):
    from app.core.graph_store import get_graph_store

    _, teacher, _, sid = school
    get_graph_store(sid).add_topic("photosynthesis", name="Photosynthesis")
    r = submit(teacher, sid, short(topic_ids=["photosynthesis", "photosynthesis"]))
    assert r.status_code == 200
    assert r.json()["question"]["topic_ids"] == ["photosynthesis"]  # de-duplicated


# ---------- diagrams / pictures ----------


def test_a_diagram_can_be_attached_to_any_question_type(school, upload_image):
    _, teacher, _, sid = school
    image_id = upload_image(teacher)
    for case in (mcq(), short(), {**short(), "question_type": "stem_diagram"}):
        r = submit(teacher, sid, {**case, "diagram": {"image_id": image_id, "caption": "  Figure 1  "}})
        assert r.status_code == 200, r.text
        d = r.json()["question"]["diagram"]
        assert d["kind"] == "image" and d["image_id"] == image_id and d["caption"] == "Figure 1"
        assert d["render_error"] is None


def worksheet(upload_image, teacher, **over):
    base = {
        "text": "Circle the animals",
        "question_type": "visual_worksheet",
        "marks": 1,
        "bloom_level": 4,  # ignored: worksheets are always recall
        "grid_layout": {
            "kind": "single_row",
            "response_style": "circle_choice",
            "items": [
                {"image_id": upload_image(teacher), "label": "Dog", "is_correct": True},
                {"image_id": upload_image(teacher), "label": "Chair", "is_correct": False},
                {"image_id": upload_image(teacher), "label": "Cat", "is_correct": True},
            ],
        },
    }
    return {**base, **over}


def test_visual_worksheet_with_uploaded_pictures(school, upload_image):
    _, teacher, _, sid = school
    r = submit(teacher, sid, worksheet(upload_image, teacher))
    assert r.status_code == 200, r.text
    q = r.json()["question"]
    assert q["bloom_level"] == 1
    layout = q["grid_layout"]
    assert layout["instruction"] == "Circle the animals"
    assert [i["label"] for i in layout["items"]] == ["Dog", "Chair", "Cat"]
    assert all(i["visual"]["image_id"] for i in layout["items"])
    assert [i["is_correct"] for i in layout["items"]] == [True, False, True]


def test_visual_worksheet_validation(school, upload_image):
    _, teacher, _, sid = school
    no_grid = {"text": "Circle", "question_type": "visual_worksheet", "marks": 1}
    assert submit(teacher, sid, no_grid).status_code == 422

    one_item = worksheet(upload_image, teacher)
    one_item["grid_layout"]["items"] = one_item["grid_layout"]["items"][:1]
    assert submit(teacher, sid, one_item).status_code == 422

    nothing_correct = worksheet(upload_image, teacher)
    for item in nothing_correct["grid_layout"]["items"]:
        item["is_correct"] = False
    r = submit(teacher, sid, nothing_correct)
    assert r.status_code == 422 and "circle" in r.json()["detail"].lower()

    # "blank line" worksheets don't need a correct picture
    blank = worksheet(upload_image, teacher)
    blank["grid_layout"]["response_style"] = "blank_line"
    for item in blank["grid_layout"]["items"]:
        item["is_correct"] = None
    assert submit(teacher, sid, blank).status_code == 200

    missing_pic = worksheet(upload_image, teacher)
    missing_pic["grid_layout"]["items"][0]["image_id"] = "f" * 32
    assert submit(teacher, sid, missing_pic).status_code == 422

    with_diagram = worksheet(upload_image, teacher, diagram={"image_id": upload_image(teacher)})
    assert submit(teacher, sid, with_diagram).status_code == 422


# ---------- listing / visibility ----------


def test_teachers_only_see_their_own_submissions(school, make_teacher):
    admin, teacher, teacher_id, sid = school
    other, other_id = make_teacher(email="other@school.edu", name="Other", subject_ids=[sid])
    mine = submit(teacher, sid, mcq()).json()
    theirs = submit(other, sid, short()).json()

    assert [s["id"] for s in teacher.get("/api/v1/submissions").json()] == [mine["id"]]
    assert [s["id"] for s in other.get("/api/v1/submissions").json()] == [theirs["id"]]
    # a teacher can't widen this by passing someone else's id
    assert [s["id"] for s in teacher.get("/api/v1/submissions", params={"teacher_id": other_id}).json()] == [mine["id"]]
    assert {s["id"] for s in admin.get("/api/v1/submissions").json()} == {mine["id"], theirs["id"]}


def test_a_teacher_cannot_read_edit_or_delete_anothers_submission(school, make_teacher):
    admin, teacher, _, sid = school
    other, _ = make_teacher(email="other@school.edu", name="Other", subject_ids=[sid])
    sub = submit(teacher, sid, mcq()).json()
    url = f"/api/v1/submissions/{sub['id']}"

    assert other.get(url).status_code == 404
    assert other.put(url, json={"question": mcq()}).status_code == 404
    assert other.delete(url).status_code == 404
    assert admin.get(url).status_code == 200  # but the admin can read it
    assert admin.put(url, json={"question": mcq()}).status_code == 404  # only the author edits


def test_admin_filters(api_client, make_teacher, upload_image):
    admin = api_client
    maths = admin.post("/api/v1/subjects", json={"name": "Maths", "grade": "7"}).json()
    t1, t1_id = make_teacher(email="t1@school.edu", name="T1", subject_ids=[admin.subject_id, maths["id"]])
    t2, t2_id = make_teacher(email="t2@school.edu", name="T2", subject_ids=[admin.subject_id])

    a = submit(t1, admin.subject_id, mcq()).json()
    b = submit(t1, maths["id"], short(text="Define a prime number.")).json()
    c = submit(t2, admin.subject_id, {**short(), "question_type": "long_answer", "marks": 7, "text": "Explain the water cycle."}).json()
    admin.post(f"/api/v1/submissions/{a['id']}/review", json={"decision": "accept"})

    def ids(**params):
        return {s["id"] for s in admin.get("/api/v1/submissions", params=params).json()}

    assert ids() == {a["id"], b["id"], c["id"]}
    assert ids(subject_id=maths["id"]) == {b["id"]}
    assert ids(grade="5") == {a["id"], c["id"]}
    assert ids(grade="7") == {b["id"]}
    assert ids(teacher_id=t2_id) == {c["id"]}
    assert ids(status="accepted") == {a["id"]}
    assert ids(status="submitted") == {b["id"], c["id"]}
    assert ids(question_type="long_answer") == {c["id"]}
    assert ids(q="PRIME") == {b["id"]}  # case-insensitive text search
    assert ids(grade="5", status="submitted") == {c["id"]}
    assert ids(q="nothing matches this") == set()
    assert len(admin.get("/api/v1/submissions", params={"limit": 2}).json()) == 2
    assert admin.get("/api/v1/submissions", params={"status": "bogus"}).status_code == 422


def test_summary_counts(school, make_teacher):
    admin, teacher, _, sid = school
    other, _ = make_teacher(email="other@school.edu", name="Other", subject_ids=[sid])
    a = submit(teacher, sid, mcq()).json()
    b = submit(teacher, sid, short(text="Another question?")).json()
    submit(other, sid, short(text="Third one.", correct_answer="x"))
    admin.post(f"/api/v1/submissions/{a['id']}/review", json={"decision": "accept"})
    admin.post(f"/api/v1/submissions/{b['id']}/review", json={"decision": "request_changes", "comment": "clarify"})

    assert admin.get("/api/v1/submissions/summary").json() == {"submitted": 1, "changes_requested": 1, "accepted": 1, "rejected": 0}
    # a teacher's summary counts only their own
    assert teacher.get("/api/v1/submissions/summary").json() == {"submitted": 0, "changes_requested": 1, "accepted": 1, "rejected": 0}
    assert other.get("/api/v1/submissions/summary").json() == {"submitted": 1, "changes_requested": 0, "accepted": 0, "rejected": 0}


# ---------- review ----------


def test_accept_puts_the_question_in_the_bank_credited_to_the_author(school):
    admin, teacher, teacher_id, sid = school
    sub = submit(teacher, sid, mcq()).json()

    r = admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept", "comment": "Nice one"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "accepted"
    assert body["admin_comment"] == "Nice one"
    assert [e["kind"] for e in body["history"]] == ["submitted", "accepted"]

    bank = admin.get("/api/v1/questions", params={"subject_id": sid}).json()
    banked = next(q for q in bank if q["id"] == sub["question"]["id"])  # same id as the submission's question
    assert banked["author_id"] == teacher_id
    assert banked["text"] == "Which of these is a mammal?"
    assert banked["correct_answer"] == "Whale"
    assert banked["difficulty_score"] is not None  # scored on acceptance
    assert 1.0 <= banked["difficulty_score"] <= 10.0


def test_accepting_a_worksheet_skips_scoring_like_generated_ones(school, upload_image):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, worksheet(upload_image, teacher)).json()
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    banked = next(q for q in admin.get("/api/v1/questions", params={"subject_id": sid}).json() if q["id"] == sub["question"]["id"])
    assert banked["difficulty_score"] is None
    assert banked["grid_layout"]["items"][0]["visual"]["image_id"]


def test_reject_does_not_touch_the_bank(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    r = admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "reject", "comment": "Too easy"})
    assert r.json()["status"] == "rejected" and r.json()["admin_comment"] == "Too easy"
    assert admin.get("/api/v1/questions", params={"subject_id": sid}).json() == []
    # the teacher sees the outcome and the reason
    mine = teacher.get(f"/api/v1/submissions/{sub['id']}").json()
    assert mine["status"] == "rejected" and mine["admin_comment"] == "Too easy"


def test_reject_without_a_comment_is_allowed_but_request_changes_needs_one(school):
    admin, teacher, _, sid = school
    a = submit(teacher, sid, mcq()).json()
    b = submit(teacher, sid, short()).json()
    assert admin.post(f"/api/v1/submissions/{a['id']}/review", json={"decision": "reject"}).status_code == 200
    r = admin.post(f"/api/v1/submissions/{b['id']}/review", json={"decision": "request_changes"})
    assert r.status_code == 422
    assert admin.post(f"/api/v1/submissions/{b['id']}/review", json={"decision": "request_changes", "comment": "   "}).status_code == 422
    assert admin.get(f"/api/v1/submissions/{b['id']}").json()["status"] == "submitted"  # unchanged by the failures


def test_a_submission_can_only_be_reviewed_once(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    url = f"/api/v1/submissions/{sub['id']}/review"
    assert admin.post(url, json={"decision": "accept"}).status_code == 200
    assert admin.post(url, json={"decision": "accept"}).status_code == 409
    assert admin.post(url, json={"decision": "reject"}).status_code == 409
    bank = admin.get("/api/v1/questions", params={"subject_id": sid}).json()
    assert len([q for q in bank if q["id"] == sub["question"]["id"]]) == 1  # not added twice


def test_teachers_cannot_review(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    assert teacher.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"}).status_code == 403
    assert admin.get(f"/api/v1/submissions/{sub['id']}").json()["status"] == "submitted"
    assert admin.get("/api/v1/questions", params={"subject_id": sid}).json() == []


def test_review_unknown_submission_is_404_and_bad_decision_422(school):
    admin, teacher, _, sid = school
    assert admin.post("/api/v1/submissions/nope/review", json={"decision": "accept"}).status_code == 404
    sub = submit(teacher, sid, mcq()).json()
    assert admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "maybe"}).status_code == 422


def test_cannot_accept_when_the_subject_was_deleted(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    admin.delete(f"/api/v1/subjects/{sid}")
    r = admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    assert r.status_code == 409
    shown = admin.get(f"/api/v1/submissions/{sub['id']}").json()
    assert shown["subject_name"] == "(deleted subject)" and shown["status"] == "submitted"


# ---------- editing, changes requested, resubmitting ----------


def test_changes_requested_then_resubmit_flow(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    url = f"/api/v1/submissions/{sub['id']}"

    admin.post(f"{url}/review", json={"decision": "request_changes", "comment": "Add a fourth option"})
    seen = teacher.get(url).json()
    assert seen["status"] == "changes_requested" and seen["admin_comment"] == "Add a fourth option"

    fixed = mcq(options=["Frog", "Whale", "Shark", "Eagle"])
    r = teacher.put(url, json={"question": fixed})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "submitted"
    assert body["revision"] == 2
    assert body["admin_comment"] is None  # old feedback no longer applies
    assert body["question"]["options"] == ["Frog", "Whale", "Shark", "Eagle"]
    assert body["question"]["id"] == sub["question"]["id"]  # same question, new revision
    assert [e["kind"] for e in body["history"]] == ["submitted", "changes_requested", "resubmitted"]
    assert body["history"][1]["comment"] == "Add a fourth option"

    assert admin.post(f"{url}/review", json={"decision": "accept"}).json()["status"] == "accepted"


def test_editing_before_review_keeps_it_pending(school):
    _, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    r = teacher.put(f"/api/v1/submissions/{sub['id']}", json={"question": mcq(text="Which animal is a mammal?")})
    body = r.json()
    assert body["status"] == "submitted" and body["revision"] == 1
    assert body["question"]["text"] == "Which animal is a mammal?"
    assert body["history"][-1]["kind"] == "edited"


def test_edit_is_validated_and_a_failed_edit_changes_nothing(school):
    _, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    url = f"/api/v1/submissions/{sub['id']}"
    assert teacher.put(url, json={"question": mcq(options=["one"], correct_answer="one")}).status_code == 422
    assert teacher.get(url).json()["question"]["options"] == ["Frog", "Whale", "Shark"]


def test_reviewed_submissions_cannot_be_edited(school):
    admin, teacher, _, sid = school
    accepted = submit(teacher, sid, mcq()).json()
    rejected = submit(teacher, sid, short()).json()
    admin.post(f"/api/v1/submissions/{accepted['id']}/review", json={"decision": "accept"})
    admin.post(f"/api/v1/submissions/{rejected['id']}/review", json={"decision": "reject"})
    assert teacher.put(f"/api/v1/submissions/{accepted['id']}", json={"question": mcq()}).status_code == 409
    assert teacher.put(f"/api/v1/submissions/{rejected['id']}", json={"question": short()}).status_code == 409


def test_edit_cannot_change_the_subject_or_author(school):
    _, teacher, teacher_id, sid = school
    sub = submit(teacher, sid, mcq()).json()
    r = teacher.put(f"/api/v1/submissions/{sub['id']}", json={"subject_id": "other", "teacher_id": "x", "question": mcq()})
    assert r.json()["subject_id"] == sid and r.json()["teacher_id"] == teacher_id


# ---------- deleting ----------


def test_author_can_delete_until_accepted(school):
    admin, teacher, _, sid = school
    pending = submit(teacher, sid, mcq()).json()
    accepted = submit(teacher, sid, short()).json()
    admin.post(f"/api/v1/submissions/{accepted['id']}/review", json={"decision": "accept"})

    assert teacher.delete(f"/api/v1/submissions/{pending['id']}").status_code == 200
    assert teacher.get(f"/api/v1/submissions/{pending['id']}").status_code == 404
    assert teacher.delete(f"/api/v1/submissions/{accepted['id']}").status_code == 409
    assert admin.delete(f"/api/v1/submissions/{accepted['id']}").status_code == 409  # not even the admin
    assert teacher.delete("/api/v1/submissions/nope").status_code == 404


def test_admin_can_delete_a_rejected_submission(school):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, mcq()).json()
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "reject"})
    assert admin.delete(f"/api/v1/submissions/{sub['id']}").status_code == 200


def test_cannot_delete_a_teacher_who_has_submissions(school):
    admin, teacher, teacher_id, sid = school
    submit(teacher, sid, mcq())
    r = admin.delete(f"/api/v1/admin/teachers/{teacher_id}")
    assert r.status_code == 409 and "deactivate" in r.json()["detail"].lower()
    assert teacher_id in {t["id"] for t in admin.get("/api/v1/admin/teachers").json()}


# ---------- duplicate warnings (admin only) ----------


def test_admin_sees_a_similar_banked_question_but_the_teacher_does_not(school, make_teacher):
    admin, teacher, _, sid = school
    first = submit(teacher, sid, short(text="What is photosynthesis and why do plants need it?")).json()
    admin.post(f"/api/v1/submissions/{first['id']}/review", json={"decision": "accept"})

    other, _ = make_teacher(email="other@school.edu", name="Other", subject_ids=[sid])
    second = submit(other, sid, short(text="What is photosynthesis and why do plants need it?")).json()

    assert second["duplicate_hits"] == []  # the submitting teacher is told nothing
    hits = admin.get(f"/api/v1/submissions/{second['id']}").json()["duplicate_hits"]
    assert len(hits) == 1
    assert hits[0]["where"] == "bank"
    assert hits[0]["question_id"] == first["question"]["id"]
    assert hits[0]["similarity"] >= 0.95  # identical text
    assert "photosynthesis" in hits[0]["text"].lower()
    # ...and the teacher still sees nothing when reading it back
    assert other.get(f"/api/v1/submissions/{second['id']}").json()["duplicate_hits"] == []


def test_admin_sees_a_similar_pending_submission(school, make_teacher):
    admin, teacher, _, sid = school
    first = submit(teacher, sid, short(text="Explain the water cycle in your own words.")).json()
    other, _ = make_teacher(email="other@school.edu", name="Other", subject_ids=[sid])
    second = submit(other, sid, short(text="Explain the water cycle in your own words.")).json()

    hits = admin.get(f"/api/v1/submissions/{second['id']}").json()["duplicate_hits"]
    assert [h["where"] for h in hits] == ["pending"]
    assert hits[0]["question_id"] == first["question"]["id"]


def test_unrelated_questions_are_not_flagged(school):
    admin, teacher, _, sid = school
    submit(teacher, sid, short(text="Name the capital of France."))
    second = submit(teacher, sid, short(text="Describe how a volcano erupts.")).json()
    assert admin.get(f"/api/v1/submissions/{second['id']}").json()["duplicate_hits"] == []


# ---------- topics endpoint (teacher-safe window into the graph) ----------


def test_teacher_can_list_topics_for_an_assigned_subject_only(api_client, make_teacher):
    from app.core.graph_store import get_graph_store

    other = api_client.post("/api/v1/subjects", json={"name": "Maths", "grade": "6"}).json()
    graph = get_graph_store(api_client.subject_id)
    graph.add_topic("b_topic", name="Beta")
    graph.add_topic("a_topic", name="alpha")
    teacher, _ = make_teacher(subject_ids=[api_client.subject_id])

    r = teacher.get(f"/api/v1/subjects/{api_client.subject_id}/topics")
    assert r.status_code == 200
    assert r.json() == [{"id": "a_topic", "name": "alpha"}, {"id": "b_topic", "name": "Beta"}]  # sorted, names only
    assert teacher.get(f"/api/v1/subjects/{other['id']}/topics").status_code == 404
    assert api_client.get(f"/api/v1/subjects/{other['id']}/topics").status_code == 200  # admin: any subject


# ---------- exports render attached pictures ----------


def test_exports_render_an_uploaded_diagram_on_any_question_type(school, upload_image):
    admin, teacher, _, sid = school
    image_id = upload_image(teacher, size=(300, 200))
    sub = submit(teacher, sid, {**mcq(), "diagram": {"image_id": image_id, "caption": "Figure 1"}}).json()
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})

    bp = admin.post(
        "/api/v1/paper/blueprints",
        json={
            "subject_id": sid,
            "name": "Unit test",
            "total_marks": 2,
            "sections": [{"title": "A", "question_format": "mcq", "question_ids": [sub["question"]["id"]]}],
        },
    ).json()

    pdf = admin.get(f"/api/v1/paper/blueprints/{bp['id']}/export", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    docx = admin.get(f"/api/v1/paper/blueprints/{bp['id']}/export", params={"format": "docx"})
    assert docx.status_code == 200 and docx.content[:2] == b"PK"

    # And the picture really made it in: the PDF is bigger than the same paper without it.
    plain = submit(teacher, sid, mcq(text="Which is a mammal? (no figure)")).json()
    admin.post(f"/api/v1/submissions/{plain['id']}/review", json={"decision": "accept"})
    bp2 = admin.post(
        "/api/v1/paper/blueprints",
        json={"subject_id": sid, "name": "Plain", "total_marks": 2, "sections": [{"title": "A", "question_format": "mcq", "question_ids": [plain["question"]["id"]]}]},
    ).json()
    plain_pdf = admin.get(f"/api/v1/paper/blueprints/{bp2['id']}/export", params={"format": "pdf"})
    assert len(pdf.content) > len(plain_pdf.content) + 500


def test_worksheet_with_uploaded_pictures_exports(school, upload_image):
    admin, teacher, _, sid = school
    sub = submit(teacher, sid, worksheet(upload_image, teacher)).json()
    admin.post(f"/api/v1/submissions/{sub['id']}/review", json={"decision": "accept"})
    bp = admin.post(
        "/api/v1/paper/blueprints",
        json={"subject_id": sid, "name": "LKG", "total_marks": 1, "sections": [{"title": "A", "question_format": "visual_worksheet", "question_ids": [sub["question"]["id"]]}]},
    ).json()
    for fmt, magic in (("pdf", b"%PDF"), ("docx", b"PK")):
        r = admin.get(f"/api/v1/paper/blueprints/{bp['id']}/export", params={"format": fmt})
        assert r.status_code == 200 and r.content[:len(magic)] == magic, fmt
