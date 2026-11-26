import base64
import json
from os import urandom

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from test_outputs import run_group
from test_worker import claim_body, setup_job

from comfyshop_api.main import create_app
from comfyshop_api.models import WebPushDelivery, WebPushSubscription, now_ms
from comfyshop_api.services import web_push

PATH = "/api/v1/web-push"


@pytest.fixture
def push_client(settings, monkeypatch):
    monkeypatch.setattr("comfyshop_api.main.deliver_task_notifications", lambda *_: None)
    with TestClient(create_app(settings), headers={"Origin": "http://testserver"}) as client:
        credentials = {"username": "push-owner", "password": "browser-test-password"}
        login = client.post("/api/v1/auth/register", json=credentials).raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
        yield client, credentials


def browser_subscription():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    auth = urandom(16)
    return (
        private,
        auth,
        {
            "endpoint": "https://fcm.googleapis.com/fcm/send/comfyshop-test",
            "p256dh": base64.urlsafe_b64encode(public).decode().rstrip("="),
            "auth": base64.urlsafe_b64encode(auth).decode().rstrip("="),
        },
    )


def test_browser_push_belongs_to_the_current_login(push_client, settings):
    client, credentials = push_client
    _, _, subscription = browser_subscription()
    preference = client.get(PATH).raise_for_status().json()
    assert not preference["enabled"]
    assert preference["publicKey"] == web_push.public_key(web_push.load_key(settings.data_dir))
    assert (settings.data_dir / "web-push-key.pem").stat().st_mode & 0o777 == 0o600
    for endpoint in (
        "http://fcm.googleapis.com/fcm/send/test",
        "https://example.com/notification",
        "https://fcm.googleapis.com.example.com/fcm/send/test",
    ):
        assert client.put(PATH, json={**subscription, "endpoint": endpoint}).status_code == 422
    assert (
        client.put(PATH, json=subscription, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    )
    assert client.put(PATH, json=subscription).status_code == 204
    assert client.get(PATH).json()["enabled"]
    other = TestClient(client.app, headers={"Origin": "http://testserver"})
    assert other.get(PATH).status_code == 401
    new_account = other.post(
        "/api/v1/auth/register", json={**credentials, "username": "duplicate-endpoint"}
    ).raise_for_status()
    other.headers["X-CSRF-Token"] = new_account.json()["csrfToken"]
    assert other.put(PATH, json=subscription).status_code == 409
    assert client.get(PATH).json()["enabled"]
    assert client.post("/api/v1/auth/logout").status_code == 204
    login = client.post("/api/v1/auth/login", json=credentials).raise_for_status()
    client.headers["X-CSRF-Token"] = login.json()["csrfToken"]
    assert client.get(PATH).json() == preference
    assert client.delete(PATH).status_code == 204


@pytest.mark.parametrize("settings", ["sqlite", "postgresql"], indirect=True)
def test_successful_task_sends_encrypted_notification_and_retries(push_client, settings, graph):
    client, _ = push_client
    private, auth, subscription = browser_subscription()
    assert client.put(PATH, json=subscription).status_code == 204
    assert client.put(PATH, json=subscription).status_code == 204
    machine, task, _ = setup_job(client, graph)
    worker = TestClient(client.app, headers={"Authorization": "Bearer " + machine["apiKey"]})
    claim = claim_body()
    claimed = worker.post("/api/v1/worker/claim", json=claim).raise_for_status()
    assert claimed.json()["task"]["id"] == task["id"]
    run_group(client, worker, task["id"], claim["leaseSecret"], members=1)
    assert (
        worker.post(
            f"/api/v1/worker/tasks/{task['id']}/complete",
            headers={"X-Task-Lease": claim["leaseSecret"]},
        ).json()["status"]
        == "succeeded"
    )

    deliveries = []

    def receive(request):
        assert request.url == subscription["endpoint"]
        assert request.headers["Authorization"].startswith("vapid t=")
        assert request.headers["Content-Encoding"] == "aes128gcm"
        assert request.headers["Topic"] == task["id"].replace("-", "")
        payload = http_ece.decrypt(
            request.content, private_key=private, auth_secret=auth, version="aes128gcm"
        )
        deliveries.append(json.loads(payload))
        return httpx.Response(503 if len(deliveries) == 1 else 201)

    with (
        Session(client.app.state.engine) as db,
        httpx.Client(transport=httpx.MockTransport(receive)) as provider,
    ):
        key = web_push.load_key(settings.data_dir)
        (pending,) = db.scalars(select(WebPushDelivery)).all()
        delivery_id = pending.id
        db.rollback()
        web_push.deliver_task_notifications(db, provider, key, settings)
        retry = db.get(WebPushDelivery, delivery_id)
        assert retry and retry.attempts == 1 and retry.retry_at > now_ms()
        db.execute(update(WebPushDelivery).values(retry_at=now_ms()))
        db.commit()
        web_push.deliver_task_notifications(db, provider, key, settings)
        assert db.get(WebPushDelivery, delivery_id) is None
        assert db.scalar(select(WebPushSubscription)) is not None

    assert (
        deliveries
        == [
            {
                "title": "生成完成",
                "body": "新成品已就绪，打开任务查看。",
                "url": f"/workspace/tasks?task={task['id']}&space=personal",
                "tag": task["id"].replace("-", ""),
            }
        ]
        * 2
    )
