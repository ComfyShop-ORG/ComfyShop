import logging
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from helpers import machine_heartbeat
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from comfyshop_api.api import auth
from comfyshop_api.core.config import Settings
from comfyshop_api.models import PasswordReset, User

PASSWORD = "correct-horse-battery"


def register(client, username="owner"):
    session = client.post(
        "/api/v1/auth/register", json={"username": username, "password": PASSWORD}
    ).json()
    client.headers["X-CSRF-Token"] = session["csrfToken"]
    return session


def request_email(client, email):
    """填写邮箱，返回响应和确认邮件里的凭据（没有发信时为 `None`）。"""
    sent = []
    original = auth.send_mail
    auth.send_mail = lambda *args: sent.append(args)
    try:
        response = client.put("/api/v1/auth/email", json={"email": email, "password": PASSWORD})
    finally:
        auth.send_mail = original
    found = re.search(r"/confirm-email\?token=(\S+)", sent[-1][3]) if sent else None
    return response, found.group(1) if found else None


def bind(client, email="owner@example.com"):
    """填写邮箱并用确认邮件里的链接完成绑定。"""
    response, token = request_email(client, email)
    assert response.status_code == 200, response.text
    assert client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 204


def login(client, password, username="owner"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


@pytest.fixture
def reset_token(client, monkeypatch):
    register(client)
    bind(client)
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda *args: sent.append(args))
    assert (
        client.post("/api/v1/auth/password-reset", json={"email": "owner@example.com"}).status_code
        == 204
    )
    return re.search(r"/reset-password\?token=(\S+)", sent[0][3]).group(1)


@pytest.mark.parametrize(
    ("language", "locale", "subject"),
    [
        ("en", "en", "Reset your ComfyShop password"),
        ("zh-tw", "zh-TW", "重設 ComfyShop 密碼"),
        ("ja", "ja-JP", "ComfyShop のパスワード再設定"),
        ("ko", "ko-KR", "ComfyShop 비밀번호 재설정"),
    ],
)
def test_reset_mail_uses_the_configured_address_and_language(
    client, settings, monkeypatch, language, locale, subject
):
    register(client)
    bind(client)
    settings.public_url = "https://comfyshop.example.com"
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda *args: sent.append(args))
    response = client.post(
        "/api/v1/auth/password-reset",
        json={"email": "owner@example.com"},
        headers={
            "Host": "untrusted.example",
            "Origin": "http://untrusted.example",
            "Accept-Language": language,
        },
    )
    assert response.status_code == 204
    assert len(sent) == 1
    assert sent[0][2] == subject
    for body in sent[0][3:]:
        assert "https://comfyshop.example.com/reset-password?token=" in body
        assert "untrusted.example" not in body
    assert f'<html lang="{locale}">' in sent[0][4]


def test_sending_mail_without_a_trusted_site_never_issues_credentials(
    client, settings, monkeypatch
):
    register(client)
    bind(client)
    settings.public_url = None
    settings.smtp_host = "smtp.example.com"
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda *args: sent.append(args))
    for email in ("owner@example.com", "unknown@example.com"):
        response = client.post(
            "/api/v1/auth/password-reset",
            json={"email": email},
            headers={"Host": "untrusted.example", "Origin": "http://untrusted.example"},
        )
        assert response.status_code == 503
    assert sent == []
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(PasswordReset.token_hash)) is None


def test_without_mail_or_site_the_log_gets_a_path_on_this_platform(client, settings, caplog):
    """开发环境不配置邮件和平台地址也能找回密码，日志里的链接不带请求的 Host。"""
    register(client)
    bind(client)
    settings.public_url = None
    settings.smtp_host = None
    with caplog.at_level(logging.WARNING, logger="comfyshop.mail"):
        response = client.post(
            "/api/v1/auth/password-reset",
            json={"email": "owner@example.com"},
            headers={"Host": "untrusted.example", "Origin": "http://untrusted.example"},
        )
    assert response.status_code == 204
    assert "untrusted.example" not in caplog.text
    token = re.search(r"(?m)^/reset-password\?token=(\S+)", caplog.text).group(1)
    confirm = {"token": token, "password": "recovered-password-1"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=confirm).status_code == 204


@pytest.mark.parametrize(
    "value", ["javascript:alert(1)", "https://user:pass@example.com", "https://example.com?next=x"]
)
def test_reset_site_requires_an_http_address_without_credentials_or_query(value):
    with pytest.raises(ValidationError):
        Settings(public_url=value)


def test_concurrent_reset_consumes_the_token_once(client, reset_token, monkeypatch):
    # 两个请求都读到原凭据后再继续，保证覆盖旧实现中的并发窗口。
    ready = Barrier(2)
    get = Session.get

    def concurrent_read(db, model, *args, **kwargs):
        result = get(db, model, *args, **kwargs)
        if model is PasswordReset and not kwargs.get("populate_existing"):
            ready.wait(timeout=10)
        return result

    monkeypatch.setattr(Session, "get", concurrent_read)
    body = {"token": reset_token, "password": "concurrent-reset-password"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [
            pool.submit(client.post, "/api/v1/auth/password-reset/confirm", json=body)
            for _ in range(2)
        ]
        assert sorted(request.result().status_code for request in requests) == [204, 400]
    assert login(client, body["password"]).status_code == 200


@pytest.mark.parametrize("email", [None, "replacement@example.com"])
def test_changing_the_recovery_email_revokes_existing_tokens(client, reset_token, email):
    # 解除绑定立即生效；换成新邮箱要等确认，确认之后旧邮箱收到的链接才作废。
    if email:
        bind(client, email)
    else:
        assert request_email(client, None)[0].status_code == 200
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "unwanted-password"},
    )
    assert response.status_code == 400
    assert login(client, PASSWORD).status_code == 200


def test_changing_the_password_needs_the_current_one_and_replaces_it(client):
    register(client)
    wrong = client.post(
        "/api/v1/auth/password",
        json={"currentPassword": "not-the-password", "newPassword": "a-brand-new-password"},
    )
    assert wrong.status_code == 403
    changed = client.post(
        "/api/v1/auth/password",
        json={"currentPassword": PASSWORD, "newPassword": "a-brand-new-password"},
    )
    assert changed.status_code == 204
    # 当前设备保持登录。
    assert client.get("/api/v1/auth/session").json()["user"]["username"] == "owner"
    assert login(client, PASSWORD).status_code == 401
    assert login(client, "a-brand-new-password").status_code == 200


def test_password_reset_mail_carries_a_single_use_link(client, monkeypatch):
    register(client)
    bind(client, " Owner@Example.com ")
    assert client.get("/api/v1/auth/session").json()["user"]["email"] == "Owner@Example.com"
    sent = []
    monkeypatch.setattr(
        auth, "send_mail", lambda settings, to, subject, body, html: sent.append((to, body, html))
    )
    assert (
        client.put("/api/v1/auth/email", json={"email": "nope", "password": PASSWORD}).status_code
        == 422
    )

    # 没有绑定账号的邮箱得到同样的响应，也不会发信。
    assert (
        client.post("/api/v1/auth/password-reset", json={"email": "other@example.com"}).status_code
        == 204
    )
    assert sent == []
    assert (
        client.post("/api/v1/auth/password-reset", json={"email": "owner@example.com"}).status_code
        == 204
    )
    ((to, body, html),) = sent
    assert to == "Owner@Example.com"
    token = re.search(r"http://testserver/reset-password\?token=(\S+)", body).group(1)
    # 主题样式的正文带同一个链接和品牌名。
    assert f'href="http://testserver/reset-password?token={token}"' in html and "ComfyShop" in html

    confirm = {"token": token, "password": "recovered-password-1"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=confirm).status_code == 204
    # 重置后所有设备退出，链接不能再用。
    assert client.get("/api/v1/auth/session").json()["user"] is None
    assert client.post("/api/v1/auth/password-reset/confirm", json=confirm).status_code == 400
    assert login(client, PASSWORD).status_code == 401
    assert login(client, "recovered-password-1").status_code == 200


def test_reset_link_is_logged_when_no_mail_service_is_configured(client, caplog):
    register(client)
    bind(client)
    with caplog.at_level(logging.WARNING, logger="comfyshop.mail"):
        client.post("/api/v1/auth/password-reset", json={"email": "owner@example.com"})
    token = re.search(r"/reset-password\?token=(\S+)", caplog.text).group(1)
    confirm = {"token": token, "password": "recovered-password-1"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=confirm).status_code == 204


def test_an_email_belongs_to_one_account(client):
    register(client)
    bind(client, "shared@example.com")
    client.post("/api/v1/auth/logout")
    register(client, "second")
    # 填写时不透露邮箱是否已被绑定，确认时才拒绝：能确认的人本来就收得到这个邮箱的邮件。
    pending, token = request_email(client, "SHARED@example.com")
    assert pending.status_code == 200 and pending.json()["pendingEmail"] == "SHARED@example.com"
    taken = client.post("/api/v1/auth/email/confirm", json={"token": token})
    assert taken.status_code == 409
    assert client.get("/api/v1/auth/session").json()["user"]["email"] is None


def test_deleting_the_account_hides_its_content_and_frees_the_name(client, graph):
    register(client)
    machine = client.post("/api/v1/machines", json={"name": "工作机"}).json()
    workflow = client.post("/api/v1/workflows", json={"name": "mine", "graph": graph}).json()
    assert (
        client.post("/api/v1/auth/account/delete", json={"password": "wrong-password"}).status_code
        == 403
    )
    assert (
        client.post("/api/v1/auth/account/delete", json={"password": PASSWORD}).status_code == 204
    )
    assert client.get("/api/v1/auth/session").json()["user"] is None
    assert login(client, PASSWORD).status_code == 401
    # 工作机密钥随账号失效。
    heartbeat = client.post(
        "/api/v1/worker/heartbeat",
        json=machine_heartbeat(device="cpu"),
        headers={"Authorization": "Bearer " + machine["apiKey"]},
    )
    assert heartbeat.status_code == 401
    # 同名账号可以重新注册，看不到原账号的内容。
    register(client)
    assert client.get("/api/v1/workflows", params={"scope": "mine"}).json()["items"] == []
    assert client.get(f"/api/v1/workflows/{workflow['id']}").status_code == 404


def test_mail_theme_uses_the_design_tokens():
    import json
    from pathlib import Path

    from comfyshop_api.services.mail import COLORS

    tokens = json.loads(
        (Path(__file__).parents[3] / "packages/tokens/src/tokens.json").read_text()
    )["color"]
    assert COLORS == tokens


def test_password_checks_are_throttled_per_account(client):
    register(client)
    wrong = {"currentPassword": "not-the-password", "newPassword": "a-brand-new-password"}
    statuses = [client.post("/api/v1/auth/password", json=wrong).status_code for _ in range(11)]
    assert statuses[:10] == [403] * 10 and statuses[10] == 429
    # 换绑邮箱和注销共用同一个计数，不能换个接口继续猜。
    email = {"email": "owner@example.com", "password": PASSWORD}
    assert client.put("/api/v1/auth/email", json=email).status_code == 429


def test_no_password_hashing_happens_inside_the_write_lock(client, monkeypatch):
    """核对和生成密码哈希都在锁外，SQLite 上其他账号的写入不必等它们。"""
    from comfyshop_api.services import accounts

    register(client)
    bind(client)
    order = []
    real_verify, real_lock, real_hash = (
        accounts.verify_password,
        accounts.write_lock,
        accounts.passwords.hash,
    )
    monkeypatch.setattr(
        accounts, "verify_password", lambda *a: order.append("verify") or real_verify(*a)
    )
    monkeypatch.setattr(accounts, "write_lock", lambda *a: order.append("lock") or real_lock(*a))
    monkeypatch.setattr(
        accounts.passwords, "hash", lambda *a: order.append("hash") or real_hash(*a)
    )

    def run(request):
        order.clear()
        assert request().status_code == 204
        # 每次加锁之后都不再有哈希计算。
        assert "hash" not in order[order.index("lock") :], order
        return list(order)

    body = {"currentPassword": PASSWORD, "newPassword": "a-brand-new-password"}
    assert run(lambda: client.post("/api/v1/auth/password", json=body)) == [
        "verify",
        "hash",
        "lock",
    ]
    token = reset_token_for(client, monkeypatch)
    confirm = {"token": token, "password": "recovered-password-1"}
    run(lambda: client.post("/api/v1/auth/password-reset/confirm", json=confirm))
    # 无效链接不触发哈希计算。
    order.clear()
    assert client.post("/api/v1/auth/password-reset/confirm", json=confirm).status_code == 400
    assert "hash" not in order
    login_response = login(client, "recovered-password-1")
    client.headers["X-CSRF-Token"] = login_response.json()["csrfToken"]
    run(
        lambda: client.post(
            "/api/v1/auth/account/delete", json={"password": "recovered-password-1"}
        )
    )


def test_a_taken_name_does_not_reveal_whether_an_email_is_registered(client):
    register(client)
    bind(client)
    client.post("/api/v1/auth/logout")
    for email in ("owner@example.com", "unknown@example.com"):
        taken = client.post(
            "/api/v1/auth/register",
            json={"username": "owner", "password": PASSWORD, "email": email},
        )
        assert (taken.status_code, taken.json()["detail"]) == (409, "账号已存在")


def test_registration_binds_the_email_only_after_confirmation(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda *args: sent.append(args))
    session = client.post(
        "/api/v1/auth/register",
        json={"username": "owner", "password": PASSWORD, "email": " Owner@Example.com "},
    )
    assert session.status_code == 201
    user = session.json()["user"]
    assert (user["email"], user["pendingEmail"]) == (None, "Owner@Example.com")
    assert sent[0][1] == "Owner@Example.com"
    token = re.search(r"/confirm-email\?token=(\S+)", sent[0][3]).group(1)
    # 确认之前这个邮箱不能用来找回密码。
    client.post("/api/v1/auth/password-reset", json={"email": "owner@example.com"})
    assert len(sent) == 1
    # 确认不要求登录，链接只能用一次。
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": session.json()["csrfToken"]})
    assert client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 204
    assert client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 400
    # 用已绑定的邮箱注册同样成功，响应不透露它是否已被占用。
    second = client.post(
        "/api/v1/auth/register",
        json={"username": "second", "password": PASSWORD, "email": "owner@example.com"},
    )
    assert second.status_code == 201 and second.json()["user"]["pendingEmail"]
    # 不填邮箱照常注册，也不发信。
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": second.json()["csrfToken"]})
    plain = client.post("/api/v1/auth/register", json={"username": "third", "password": PASSWORD})
    assert plain.status_code == 201 and plain.json()["user"]["pendingEmail"] is None
    assert len(sent) == 2


def test_an_unconfirmed_email_keeps_the_bound_one_and_dies_with_the_password(client):
    register(client)
    bind(client)
    pending, token = request_email(client, "typo@example.com")
    user = pending.json()
    assert (user["email"], user["pendingEmail"]) == ("owner@example.com", "typo@example.com")
    # 再填一次，之前那封邮件里的链接失效。
    _, latest = request_email(client, "typo@example.com")
    assert client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 400
    # 填回已绑定的邮箱只撤销等待中的申请，不再发信。
    same, none = request_email(client, "OWNER@example.com")
    assert same.json()["pendingEmail"] is None and none is None
    assert client.post("/api/v1/auth/email/confirm", json={"token": latest}).status_code == 400
    # 改密码后等待确认的邮箱作废：它可能是盗用者填的。
    _, stale = request_email(client, "intruder@example.com")
    body = {"currentPassword": PASSWORD, "newPassword": "a-brand-new-password"}
    assert client.post("/api/v1/auth/password", json=body).status_code == 204
    assert client.post("/api/v1/auth/email/confirm", json={"token": stale}).status_code == 400
    assert client.get("/api/v1/auth/session").json()["user"]["email"] == "owner@example.com"


def test_an_expired_confirmation_link_is_refused(client, settings):
    register(client)
    _, token = request_email(client, "owner@example.com")
    with Session(client.app.state.engine) as db:
        db.execute(update(User).values(pending_email_expires_at=0))
        db.commit()
    assert client.post("/api/v1/auth/email/confirm", json={"token": token}).status_code == 400


def test_confirmation_mail_needs_a_trusted_site(client, settings):
    register(client)
    settings.public_url = None
    settings.smtp_host = "smtp.example.com"
    response, token = request_email(client, "owner@example.com")
    assert response.status_code == 503 and token is None
    client.post("/api/v1/auth/logout")
    refused = client.post(
        "/api/v1/auth/register",
        json={"username": "second", "password": PASSWORD, "email": "second@example.com"},
    )
    assert refused.status_code == 503
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(User.id).where(User.username_key == "second")) is None


def reset_token_for(client, monkeypatch):
    """申请重置并取出邮件里的凭据，用于需要真实链接的测试。"""
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda *args: sent.append(args))
    client.post("/api/v1/auth/password-reset", json={"email": "owner@example.com"})
    return re.search(r"/reset-password\?token=(\S+)", sent[-1][3]).group(1)


def test_correct_passwords_never_lock_the_account(client):
    register(client)
    for _ in range(15):
        assert login(client, PASSWORD).status_code == 200
    statuses = [login(client, "not-the-password").status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10 and statuses[10] == 429


def test_changing_the_password_revokes_every_work_machine(client):
    register(client)
    machine = client.post("/api/v1/machines", json={"name": "工作机"}).json()
    worker = {"Authorization": "Bearer " + machine["apiKey"]}
    heartbeat = machine_heartbeat(device="cpu")
    assert (
        client.post("/api/v1/worker/heartbeat", json=heartbeat, headers=worker).status_code == 200
    )
    change = {"currentPassword": PASSWORD, "newPassword": "a-brand-new-password"}
    assert client.post("/api/v1/auth/password", json=change).status_code == 204
    assert (
        client.post("/api/v1/worker/heartbeat", json=heartbeat, headers=worker).status_code == 401
    )
    listed = client.get("/api/v1/machines").json()
    assert listed["items"][0]["revoked"] and listed["defaultMachineId"] is None
    # 重置密钥恢复这台工作机，并重新成为默认工作机。
    rotated = client.post(f"/api/v1/machines/{machine['machine']['id']}/rotate").json()
    assert not rotated["machine"]["revoked"]
    assert client.get("/api/v1/machines").json()["defaultMachineId"] == machine["machine"]["id"]
    worker = {"Authorization": "Bearer " + rotated["apiKey"]}
    assert (
        client.post("/api/v1/worker/heartbeat", json=heartbeat, headers=worker).status_code == 200
    )


def test_padding_the_email_does_not_escape_the_reset_limit(client, monkeypatch):
    monkeypatch.setattr(auth, "send_mail", lambda *args: None)
    for index in range(10):
        email = " " * index + "owner@example.com"
        response = client.post("/api/v1/auth/password-reset", json={"email": email})
        assert response.status_code == 204
    padded = client.post("/api/v1/auth/password-reset", json={"email": " owner@example.com "})
    assert padded.status_code == 429


def test_the_deleted_account_label_cannot_be_registered(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "已注销", "password": PASSWORD}
    )
    assert response.status_code == 409
