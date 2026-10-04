from datetime import UTC, datetime

from pydantic import BaseModel, Field

# Karnataka-style school: LKG, UKG, then classes 1-10.
GRADES: list[str] = ["LKG", "UKG", *[str(n) for n in range(1, 11)]]


class Subject(BaseModel):
    id: str
    teacher_id: str  # the admin who created it; access is via teacher_subjects, not this
    name: str
    grade: str | None = None  # one of GRADES; None only for subjects created before grades existed
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
