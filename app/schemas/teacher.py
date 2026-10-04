from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "teacher"]


class Teacher(BaseModel):
    id: str
    email: str
    name: str
    password_hash: str
    role: Role = "teacher"
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TeacherPublic(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    created_at: datetime

    @classmethod
    def from_teacher(cls, teacher: Teacher) -> "TeacherPublic":
        return cls(
            id=teacher.id, email=teacher.email, name=teacher.name, role=teacher.role, created_at=teacher.created_at
        )
