import io

import pytest
from PIL import Image


def make_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (40, 30), mode: str = "RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, "white").save(buf, format=fmt)
    return buf.getvalue()


def upload(client, data: bytes, name: str = "pic.png", content_type: str = "image/png"):
    return client.post("/api/v1/images", files={"file": (name, data, content_type)})


def test_upload_png_returns_id_and_is_served_back_as_png(api_client):
    r = upload(api_client, make_image_bytes())
    assert r.status_code == 200
    image_id = r.json()["image_id"]
    assert len(image_id) == 32

    got = api_client.get(f"/api/v1/images/{image_id}")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_jpeg_and_gif_and_webp_are_converted_to_real_png(api_client):
    for fmt in ("JPEG", "GIF", "WEBP"):
        r = upload(api_client, make_image_bytes(fmt), name=f"pic.{fmt.lower()}", content_type=f"image/{fmt.lower()}")
        assert r.status_code == 200, fmt
        stored = api_client.get(f"/api/v1/images/{r.json()['image_id']}").content
        assert stored[:8] == b"\x89PNG\r\n\x1a\n", fmt
        assert Image.open(io.BytesIO(stored)).format == "PNG"


def test_large_images_are_downscaled(api_client):
    r = upload(api_client, make_image_bytes(size=(3200, 2400)))
    assert r.status_code == 200
    stored = Image.open(io.BytesIO(api_client.get(f"/api/v1/images/{r.json()['image_id']}").content))
    assert max(stored.size) <= 1600
    assert stored.size == (1600, 1200)  # aspect ratio kept


def test_transparency_is_preserved(api_client):
    r = upload(api_client, make_image_bytes(size=(10, 10), mode="RGBA"))
    stored = Image.open(io.BytesIO(api_client.get(f"/api/v1/images/{r.json()['image_id']}").content))
    assert stored.mode == "RGBA"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"this is plain text, not an image",
        b"%PDF-1.4 definitely not a picture",
        b"\x89PNG\r\n\x1a\n" + b"truncated garbage",  # starts like a PNG but isn't one
    ],
)
def test_non_images_are_rejected(api_client, data):
    r = upload(api_client, data, name="evil.png", content_type="image/png")
    assert r.status_code == 422
    assert "image" in r.json()["detail"].lower()


def test_disallowed_image_format_is_rejected(api_client):
    r = upload(api_client, make_image_bytes("TIFF"), name="scan.tiff", content_type="image/tiff")
    assert r.status_code == 422


def test_oversized_upload_is_rejected_with_413(api_client):
    r = upload(api_client, b"\x00" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()


def test_upload_requires_login(api_client):
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post("/api/v1/images", files={"file": ("a.png", make_image_bytes(), "image/png")})
    assert r.status_code == 401


def test_a_teacher_can_upload(make_teacher):
    teacher, _ = make_teacher()
    assert upload(teacher, make_image_bytes()).status_code == 200
