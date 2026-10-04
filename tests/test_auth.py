from fastapi.testclient import TestClient


def test_signup_is_open_only_until_the_first_account_exists(empty_client):
    assert empty_client.get("/api/v1/auth/signup-status").json() == {"signup_open": True}

    r = empty_client.post(
        "/api/v1/auth/signup",
        json={"email": "first@school.edu", "password": "hunter22", "name": "Head Teacher"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["teacher"]["email"] == "first@school.edu"
    assert body["teacher"]["name"] == "Head Teacher"
    assert body["teacher"]["role"] == "admin"  # the first account is the admin
    assert "password_hash" not in body["teacher"]

    assert empty_client.get("/api/v1/auth/signup-status").json() == {"signup_open": False}


def test_signup_is_closed_once_an_account_exists(api_client):
    # api_client's fixture already created the first (admin) account.
    r = api_client.post(
        "/api/v1/auth/signup",
        json={"email": "stranger@school.edu", "password": "hunter22", "name": "Stranger"},
    )
    assert r.status_code == 403
    assert "closed" in r.json()["detail"].lower()

    # ...and it must not have created the account.
    login = api_client.post("/api/v1/auth/login", json={"email": "stranger@school.edu", "password": "hunter22"})
    assert login.status_code == 401


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
    assert r.json()["role"] == "admin"


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
