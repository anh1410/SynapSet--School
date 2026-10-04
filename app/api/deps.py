from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import InvalidTokenError, decode_access_token
from app.core.subject_store import get_subject_store
from app.core.teacher_store import get_teacher_store
from app.schemas.subject import Subject
from app.schemas.teacher import Teacher

_bearer_scheme = HTTPBearer()


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> Teacher:
    """Any logged-in, active account (admin or teacher)."""
    try:
        teacher_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    teacher = get_teacher_store().get(teacher_id)
    if teacher is None:
        raise HTTPException(status_code=401, detail="Teacher not found")
    if not teacher.active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    return teacher


def require_admin(teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
    """Enforced on the server so a teacher can't reach admin functionality by
    calling the API directly, whatever the UI hides."""
    if teacher.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return teacher


def require_subject(subject_id: str, teacher: Teacher) -> Subject:
    """Look up a subject the caller may use: admins can use any subject, a
    teacher only the ones an admin assigned to them. 404 (not 403) so a teacher
    can't tell that an unassigned subject's id exists."""
    subject = get_subject_store().get(subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    if teacher.role != "admin" and not get_subject_store().is_assigned(teacher.id, subject_id):
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject
