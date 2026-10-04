import io
import re
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

_VALID_ID = re.compile(r"^[a-f0-9]{32}$")  # uuid4().hex — no separators, nothing path-traversal-shaped

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_PIXELS = 40_000_000  # refuse "decompression bomb" images before decoding them fully
MAX_STORED_DIMENSION = 1600  # downscale anything bigger; plenty for a worksheet or diagram
_ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


class InvalidImageError(ValueError):
    """The uploaded bytes aren't an acceptable image; the message is safe to show a user."""


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


def save_uploaded_image(data: bytes) -> str:
    """Validate a user-uploaded picture and store it as a normalized PNG.

    The bytes are fully decoded and re-encoded rather than saved as sent, so a
    renamed non-image, a polyglot file, or odd metadata never reaches disk or a
    PDF export, and every stored image is a real PNG regardless of what was
    uploaded (the serving endpoint labels everything image/png)."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImageError(f"That image is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in _ALLOWED_FORMATS:
                raise InvalidImageError("Use a PNG, JPEG, WebP or GIF image")
            if img.width * img.height > MAX_UPLOAD_PIXELS:
                raise InvalidImageError("That image has too many pixels; please use a smaller one")
            img.load()
            has_alpha = "A" in img.getbands() or (img.mode == "P" and "transparency" in img.info)
            normalized = img.convert("RGBA" if has_alpha else "RGB")
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("That file isn't a valid image") from exc

    normalized.thumbnail((MAX_STORED_DIMENSION, MAX_STORED_DIMENSION))
    out = io.BytesIO()
    normalized.save(out, format="PNG", optimize=True)
    return save_image(out.getvalue())


def image_path(image_id: str) -> Path | None:
    """Resolve an image id to its file path, or None if the id is malformed
    or the file doesn't exist. Never joins an unvalidated id onto a path —
    `_VALID_ID` rules out '/', '\\', and '..' entirely, not just filters them."""
    if not _VALID_ID.match(image_id):
        return None
    path = _images_dir() / f"{image_id}.png"
    return path if path.exists() else None
