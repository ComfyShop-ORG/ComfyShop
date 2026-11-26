from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from sqlalchemy.orm import Session

from comfyshop_api.models import User


def image_bytes(color):
    with BytesIO() as output, Image.new("RGBA", (96, 64), color) as image:
        metadata = PngInfo()
        metadata.add_text("Description", "original metadata")
        image.save(output, format="PNG", pnginfo=metadata)
        return output.getvalue()


def test_nickname_uses_session_identity_and_can_be_cleared(authenticated):
    client = authenticated
    visitor = TestClient(client.app)
    path = "/api/v1/auth/profile"
    assert (
        visitor.put(
            path, json={"nickname": "访客"}, headers={"Origin": "http://testserver"}
        ).status_code
        == 401
    )
    assert (
        client.put(path, json={"nickname": "昵称"}, headers={"X-CSRF-Token": ""}).status_code == 403
    )
    for invalid in ("一" * 33, "两\n行", "已注销"):
        assert client.put(path, json={"nickname": invalid}).status_code == 422

    saved = client.put(path, json={"nickname": "  摄影师 📷  "}).json()
    assert saved["nickname"] == "摄影师 📷" and saved["username"] == "owner"
    assert client.get("/api/v1/authors/owner").json()["nickname"] == saved["nickname"]
    assert visitor.get("/api/v1/authors/owner").status_code == 404
    result = client.post(
        "/api/v1/auth/login", json={"username": "owner", "password": "correct-horse-battery"}
    )
    assert result.status_code == 200 and result.json()["user"]["nickname"] == saved["nickname"]
    client.headers["X-CSRF-Token"] = result.json()["csrfToken"]
    assert client.put(path, json={"nickname": " "}).json()["nickname"] is None


def test_avatar_is_re_encoded_and_replacement_retires_the_old_url(authenticated):
    client = authenticated
    visitor = TestClient(client.app)
    path = "/api/v1/auth/profile/avatar"
    first = client.put(path, content=image_bytes("red")).json()["avatarUrl"]
    assert client.get("/api/v1/auth/session").json()["user"]["avatarUrl"] == first
    assert visitor.get(first).status_code == 404
    response = client.get(first)
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, no-cache"
    assert client.get(first, headers={"If-None-Match": response.headers["etag"]}).status_code == 304
    with Image.open(BytesIO(response.content)) as image:
        assert image.size == (256, 256) and image.format == "WEBP"
        assert "Description" not in image.info

    assert client.put(path, content=b"<svg/>").status_code == 422
    assert client.put(path, content=b"a" * (5 * 1024 * 1024 + 1)).status_code == 413
    assert client.get("/api/v1/auth/session").json()["user"]["avatarUrl"] == first
    second = client.put(path, content=image_bytes("blue")).json()["avatarUrl"]
    assert second != first and client.get(first).status_code == 404
    assert client.get(second).status_code == 200
    assert client.delete(path).json()["avatarUrl"] is None
    assert client.get(second).status_code == 404


def test_account_deletion_discards_public_profile_fields(authenticated):
    client = authenticated
    assert client.put("/api/v1/auth/profile", json={"nickname": "摄影师"}).status_code == 200
    profile = client.put("/api/v1/auth/profile/avatar", content=image_bytes("red")).json()
    assert (
        client.post(
            "/api/v1/auth/account/delete", json={"password": "correct-horse-battery"}
        ).status_code
        == 204
    )
    assert client.get(profile["avatarUrl"]).status_code == 404
    with Session(client.app.state.engine) as db:
        account = db.get(User, profile["id"])
        assert account is not None
        assert account.nickname is account.avatar_digest is account.avatar_image is None
    registered = client.post(
        "/api/v1/auth/register", json={"username": "owner", "password": "a-new-password"}
    )
    assert registered.status_code == 201
    user = registered.json()["user"]
    assert user["nickname"] is None and user["avatarUrl"] is None
