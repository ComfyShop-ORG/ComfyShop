from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from comfyshop_api.main import create_app
from comfyshop_api.models import LoginSession, User
from comfyshop_api.security import COOKIE_NAME, passwords


def test_lan_access_supports_same_origin_login_and_preserves_csrf(settings):
    origin = "http://192.168.1.50:8688"
    with TestClient(create_app(settings), base_url=origin, headers={"Origin": origin}) as client:
        assert client.get("/api/v1/health").status_code == 200
        credentials = {"username": "lan-owner", "password": "correct-horse-battery"}
        assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
        login = client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        assert client.get("/api/v1/auth/session").json()["user"]["username"] == "lan-owner"
        assert client.post("/api/v1/auth/logout").status_code == 403
        client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"Origin": "https://other.example"}
            ).status_code
            == 403
        )
        assert client.post("/api/v1/auth/logout").status_code == 204


def test_registration_hashes_password_and_session_is_revocable(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "Owner", "password": "correct-horse-battery"}
    )
    assert response.status_code == 201
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    csrf = response.json()["csrfToken"]
    token = client.cookies[COOKIE_NAME]
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert passwords.verify("correct-horse-battery", user.password_hash)
        assert db.scalar(select(LoginSession)).token_hash != token
    assert "password" not in response.text.lower()
    assert client.get("/api/v1/auth/session").json()["user"]["username"] == "Owner"
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/session").json()["user"] is None
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/v1/tasks").status_code == 401


def test_wrong_password_duplicate_account_and_validation_never_echo_secrets(client):
    credentials = {"username": "owner", "password": "correct-horse-battery"}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    assert (
        client.post("/api/v1/auth/register", json={**credentials, "username": "OWNER"}).status_code
        == 409
    )
    bad = client.post("/api/v1/auth/login", json={**credentials, "password": "wrong-password"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "账号或密码错误"
    short = client.post("/api/v1/auth/register", json={"username": "other", "password": "secret"})
    assert short.status_code == 422 and "secret" not in short.text
    correct = client.post("/api/v1/auth/login", json=credentials)
    assert correct.status_code == 200


def test_csrf_origin_expiration_and_login_rate_limit(authenticated):
    client = authenticated
    assert (
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "invalid"}).status_code == 403
    )
    assert (
        client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    with Session(client.app.state.engine) as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = 0
        db.commit()
    assert client.get("/api/v1/tasks").status_code == 401
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login", json={"username": "missing", "password": "wrong-password"}
            ).status_code
            == 401
        )
    limited = client.post(
        "/api/v1/auth/login", json={"username": "missing", "password": "wrong-password"}
    )
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
