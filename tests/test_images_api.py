from app.core import image_store


def test_get_image_requires_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    anonymous = TestClient(app)
    r = anonymous.get("/api/v1/images/deadbeef00000000000000000000000")
    assert r.status_code == 401


def test_get_image_returns_saved_bytes(api_client):
    image_id = image_store.save_image(b"\x89PNGfakepngdata")

    r = api_client.get(f"/api/v1/images/{image_id}")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == b"\x89PNGfakepngdata"


def test_get_unknown_image_is_404(api_client):
    r = api_client.get("/api/v1/images/deadbeef00000000000000000000000")
    assert r.status_code == 404


def test_get_malformed_image_id_is_404(api_client):
    r = api_client.get("/api/v1/images/../../secrets")
    assert r.status_code in (404, 422)  # 422 if FastAPI's path routing rejects the traversal itself
