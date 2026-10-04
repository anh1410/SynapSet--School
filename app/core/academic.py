"""School-year and term tags. The Indian school year runs June to March, so a
question or paper made in October 2026 belongs to "2026-27" and one made in
February 2027 still does."""

from datetime import UTC, datetime

# Keep in step with TERMS in src/lib/api.ts.
TERMS = ["Term 1", "Term 2", "Annual"]


def academic_year_for(moment: datetime) -> str:
    start = moment.year if moment.month >= 6 else moment.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def current_academic_year() -> str:
    return academic_year_for(datetime.now(UTC))


def check_term(value: str | None) -> str | None:
    """None/blank means "no term"; anything else must be one of TERMS."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if value not in TERMS:
        raise ValueError(f"Term must be one of: {', '.join(TERMS)}")
    return value


def check_academic_year(value: str | None) -> str | None:
    """Accepts "2026-27" style years only (the second part must follow the first)."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    parts = value.split("-")
    if len(parts) != 2 or not (parts[0].isdigit() and len(parts[0]) == 4 and parts[1].isdigit() and len(parts[1]) == 2):
        raise ValueError('Academic year must look like "2026-27"')
    if (int(parts[0]) + 1) % 100 != int(parts[1]):
        raise ValueError('Academic year must look like "2026-27"')
    return value
