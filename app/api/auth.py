import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_teacher
from app.core.security import create_access_token, hash_password, verify_password
from app.core.teacher_store import get_teacher_store
from app.schemas.teacher import Teacher, TeacherPublic

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    teacher: TeacherPublic


class SignupStatus(BaseModel):
    signup_open: bool


@router.get("/signup-status", response_model=SignupStatus)
def signup_status() -> SignupStatus:
    """Public signup exists only to create the very first account (the admin).
    After that, admins create teacher accounts, so strangers can't register."""
    return SignupStatus(signup_open=len(get_teacher_store().list()) == 0)


@router.post("/signup", response_model=AuthResponse)
def signup(request: SignupRequest) -> AuthResponse:
    store = get_teacher_store()
    if store.list():
        raise HTTPException(
            status_code=403, detail="Signup is closed. Ask your school admin to create your account."
        )

    teacher = Teacher(
        id=str(uuid.uuid4()),
        email=request.email,
        name=request.name,
        password_hash=hash_password(request.password),
        role="admin",
    )
    store.add(teacher)
    token = create_access_token(teacher.id)
    return AuthResponse(access_token=token, teacher=TeacherPublic.from_teacher(teacher))


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest) -> AuthResponse:
    store = get_teacher_store()
    teacher = store.get_by_email(request.email)
    if teacher is None or not verify_password(request.password, teacher.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not teacher.active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    token = create_access_token(teacher.id)
    return AuthResponse(access_token=token, teacher=TeacherPublic.from_teacher(teacher))


@router.get("/me", response_model=TeacherPublic)
def me(teacher: Teacher = Depends(get_current_teacher)) -> TeacherPublic:
    return TeacherPublic.from_teacher(teacher)
