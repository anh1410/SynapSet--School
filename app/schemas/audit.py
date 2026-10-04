from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    id: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor_id: str
    actor_name: str
    action: str  # "<area>.<verb>", e.g. "question.delete"
    target_type: str = ""
    target_id: str = ""
    summary: str


class AuditPage(BaseModel):
    items: list[AuditEntry]
    has_more: bool
