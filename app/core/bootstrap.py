from collections import Counter

from app.core.subject_store import get_subject_store
from app.core.teacher_store import get_teacher_store


def ensure_admin_exists() -> None:
    """One-time upgrade for a database that predates roles: if accounts exist
    but none is an admin, promote one and keep everyone's old access.

    The admin is whoever owns the most subjects (ties go to the earliest
    account) - not simply the oldest account, which in practice is often a
    seed/test login rather than the person actually running the school.

    Every other subject owner stays assigned to the subjects they used to own,
    so nobody silently loses their subjects when ownership becomes school-wide.
    Runs only at the moment of promotion, so it can never re-add an assignment
    an admin removed on purpose later. Safe to call on every startup: it does
    nothing once an admin exists, or while there are no accounts (the first
    signup becomes the admin)."""
    teachers = get_teacher_store()
    accounts = teachers.list()  # ordered by created_at
    if not accounts or any(t.role == "admin" for t in accounts):
        return

    subjects = get_subject_store()
    all_subjects = subjects.list_all()
    owned = Counter(s.teacher_id for s in all_subjects)
    admin = max(accounts, key=lambda t: owned[t.id])  # max() keeps the first on ties
    teachers.add(admin.model_copy(update={"role": "admin"}))

    account_ids = {t.id for t in accounts}
    for subject in all_subjects:
        if subject.teacher_id != admin.id and subject.teacher_id in account_ids:
            subjects.assign(subject.teacher_id, subject.id)
