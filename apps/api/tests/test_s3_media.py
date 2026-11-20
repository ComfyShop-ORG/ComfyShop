from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import boto3
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from comfyshop_api.main import create_app
from comfyshop_api.models import Asset
from test_inputs import picture


def test_private_asset_streams_authorized_byte_ranges_from_s3(settings, monkeypatch):
    sdk = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    monkeypatch.setattr(boto3.session.Session, "client", lambda *_args, **_kwargs: sdk)
    settings.storage_backend = "s3"
    settings.s3_bucket = "test-media"
    app = create_app(settings)
    original = picture()
    with Stubber(sdk) as s3, TestClient(app, headers={"Origin": "http://testserver"}) as owner:
        credentials = {"username": "owner", "password": "correct-horse-battery"}
        session = owner.post("/api/v1/auth/register", json=credentials)
        assert session.status_code == 201
        owner.headers["X-CSRF-Token"] = session.json()["csrfToken"]
        asset_id = str(uuid4())
        s3.add_response(
            "put_object",
            {},
            {
                "Bucket": "test-media",
                "Key": ANY,
                "Body": ANY,
                "ContentLength": len(original),
                "ContentType": "image/png",
                "IfNoneMatch": "*",
            },
        )
        asset_url = f"/api/v1/assets/{asset_id}"
        uploaded = owner.put(asset_url, params={"filename": "asset.png"}, content=original)
        assert uploaded.status_code == 200
        url = uploaded.json()["media"]["src"]
        assert not settings.original_dir.exists()
        guest = TestClient(app)
        assert guest.get(url, headers={"Range": "bytes=2-9"}).status_code == 401

        with Session(app.state.engine) as db:
            key = f"originals/{db.get(Asset, asset_id).media.storage_name}"
        data = BytesIO(original[2:10])
        s3.add_response(
            "get_object",
            {
                "Body": StreamingBody(data, 8),
                "ContentLength": 8,
                "ContentRange": f"bytes 2-9/{len(original)}",
                "ETag": '"original"',
                "LastModified": datetime(2025, 1, 1, tzinfo=UTC),
            },
            {"Bucket": "test-media", "Key": key, "Range": "bytes=2-9"},
        )
        partial = owner.get(url, headers={"Range": "bytes=2-9"})
        assert partial.status_code == 206
        assert partial.content == original[2:10]
        assert partial.headers["content-range"] == f"bytes 2-9/{len(original)}"
        assert partial.headers["accept-ranges"] == "bytes"
        assert partial.headers["cache-control"] == "no-store"
        assert data.closed
        s3.add_client_error(
            "get_object",
            service_error_code="InvalidRange",
            http_status_code=416,
            expected_params={"Bucket": "test-media", "Key": key, "Range": "bytes=10000-"},
        )
        invalid = owner.get(url, headers={"Range": "bytes=10000-"})
        assert invalid.status_code == 416
        assert invalid.headers["content-range"] == f"bytes */{len(original)}"
        s3.assert_no_pending_responses()
