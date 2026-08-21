import re
import uuid
from pathlib import Path

from app.core.config import get_settings

_VALID_ID = re.compile(r"^[a-f0-9]{32}$")  # uuid4().hex — no separators, nothing path-traversal-shaped


def _images_dir() -> Path:
    settings = get_settings()
    path = Path(settings.image_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image(data: bytes) -> str:
    """Write PNG bytes to disk under a fresh content-addressable id, return that id."""
    image_id = uuid.uuid4().hex
    (_images_dir() / f"{image_id}.png").write_bytes(data)
    return image_id


def image_path(image_id: str) -> Path | None:
    """Resolve an image id to its file path, or None if the id is malformed
    or the file doesn't exist. Never joins an unvalidated id onto a path —
    `_VALID_ID` rules out '/', '\\', and '..' entirely, not just filters them."""
    if not _VALID_ID.match(image_id):
        return None
    path = _images_dir() / f"{image_id}.png"
    return path if path.exists() else None
