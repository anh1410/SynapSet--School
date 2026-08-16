from fastapi.testclient import TestClient


def test_signup_returns_token_and_teacher(api_client):
    # api_client's fixture already signed up "test@school.edu"; sign up a second account here.
    r = api_client.post(
        "/api/v1/auth/signup",
        json={"email": "new-teacher@school.edu", "password": "hunter22", "name": "Mr. Bhat"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["teacher"]["email"] == "new-teacher@school.edu"
    assert body["teacher"]["name"] == "Mr. Bhat"
    assert "password_hash" not in body["teacher"]


def test_signup_duplicate_email_rejected(api_client):
    r = api_client.post(
        "/api/v1/auth/signup",
        json={"email": "test@school.edu", "password": "somethingelse", "name": "Duplicate"},
    )
    assert r.status_code == 409


def test_login_wrong_password_rejected(api_client):
    r = api_client.post("/api/v1/auth/login", json={"email": "test@school.edu", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_email_rejected(api_client):
    r = api_client.post("/api/v1/auth/login", json={"email": "nobody@school.edu", "password": "whatever"})
    assert r.status_code == 401


def test_login_correct_credentials_succeeds(api_client):
    r = api_client.post("/api/v1/auth/login", json={"email": "test@school.edu", "password": "testpass123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_me_returns_current_teacher(api_client):
    r = api_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "test@school.edu"


def test_protected_route_without_token_is_401(api_client):
    from app.main import app

    anonymous = TestClient(app)
    r = anonymous.get("/api/v1/subjects")
    assert r.status_code == 401


def test_protected_route_with_garbage_token_is_401(api_client):
    from app.main import app

    anonymous = TestClient(app)
    r = anonymous.get("/api/v1/subjects", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
