import subprocess
import sys
from datetime import UTC, datetime, timedelta
from os import utime
from pathlib import Path
from time import time

import boto3
import pytest
from botocore.stub import ANY, Stubber

from comfyshop_media.settings import MediaSettings


def test_staging_cleanup_releases_only_dead_processes(tmp_path: Path) -> None:
    storage = MediaSettings(data_dir=tmp_path).media_storage
    script = """
import os, sys
from pathlib import Path
from comfyshop_media.settings import MediaSettings
with MediaSettings(data_dir=Path(sys.argv[1])).media_storage.staging_directory() as tmp:
    (Path(tmp) / 'partial').write_bytes(b'upload')
    os._exit(1)
"""
    with storage.staging_directory() as active:
        assert subprocess.run([sys.executable, "-c", script, str(tmp_path)]).returncode == 1
        assert len(list((tmp_path / "staging").glob("work-*"))) == 2
        storage.prune_abandoned_staging()
        assert list((tmp_path / "staging").glob("work-*")) == [Path(active)]


def test_interrupted_cross_device_restore_can_reuse_the_original_directory(tmp_path: Path) -> None:
    archive_file = tmp_path / "backup-original"
    archive_file.write_bytes(b"original")
    script = """
import errno, os, sys
from pathlib import Path
from comfyshop_media import storage
from comfyshop_media.settings import MediaSettings
root = Path(sys.argv[1])
source = root / "backup-original"
link = storage.link
def cross_device(src, dst):
    if src == source:
        raise OSError(errno.EXDEV, "separate backup volume")
    link(src, dst)
def killed(reader, writer, **kwargs):
    writer.write(reader.read(2))
    writer.flush()
    os._exit(1)
storage.link = cross_device
storage.copyfileobj = killed
MediaSettings(data_dir=root).media_storage.put("media-id", source, "image/png")
"""
    assert subprocess.run([sys.executable, "-c", script, str(tmp_path)]).returncode == 1
    storage = MediaSettings(data_dir=tmp_path).media_storage
    assert storage.restore_inventory(["media-id"]) == set()
    storage.put("media-id", archive_file, "image/png")
    with storage.local_original("media-id") as restored:
        assert restored.read_bytes() == archive_file.read_bytes()
        assert storage.restore_inventory(["media-id"]) == {"media-id"}
        assert not list(restored.parent.rglob("work-*"))


def test_regenerated_object_replaces_the_expired_derivative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    monkeypatch.setattr(boto3.session.Session, "client", lambda *_args, **_kwargs: sdk)
    settings = MediaSettings(data_dir=tmp_path, storage_backend="s3", s3_bucket="cache")
    source = tmp_path / "new"
    source.write_bytes(b"new")
    target = settings.thumbnail_dir / "image.webp"
    with Stubber(sdk) as s3:
        s3.add_response(
            "put_object",
            {},
            {
                "Bucket": "cache",
                "Key": "derived/thumbnails/image.webp",
                "Body": ANY,
                "ContentLength": 3,
                "ContentType": "image/webp",
            },
        )
        settings.media_storage.persist_derivative(source, target, "image/webp")
        s3.assert_no_pending_responses()
    assert target.read_bytes() == b"new"


def test_local_cache_expires_and_evicts_oldest_without_interrupting_reads(tmp_path: Path) -> None:
    settings = MediaSettings(
        data_dir=tmp_path, derivative_cache_max_bytes=8, derivative_cache_ttl_seconds=60
    )
    storage = settings.media_storage
    expired = settings.thumbnail_dir / "expired.webp"
    older = settings.video_preview_dir / "older.mp4"
    newest = settings.thumbnail_dir / "newest.jpg"
    original = settings.original_dir / "original"
    with storage.staging_directory() as directory:
        source = Path(directory) / "source"
        source.write_bytes(b"image")
        storage.put(original.name, source, "image/png")
        now = time()
        for target, age in [(expired, 90), (older, 30), (newest, 10)]:
            # Each entry has its own inode and modification time.
            content = source.with_name(target.stem)
            content.write_bytes(b"cache")
            storage.persist_derivative(content, target, "application/octet-stream")
            utime(target, (now - age, now - age))
        in_use = Path(directory) / "stream.mp4"
        assert not storage.reuse_derivative(expired, in_use)
        assert storage.reuse_derivative(older, in_use)
        storage.prune_local_derivatives()
        assert not expired.exists() and not older.exists()
        assert in_use.read_bytes() == newest.read_bytes() == b"cache"
        utime(newest, (now - 90, now - 90))
        storage.prune_local_derivatives()
        assert not newest.exists()
    assert original.read_bytes() == b"image"


def test_object_cache_bounds_apply_across_pages_and_only_in_derived_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    monkeypatch.setattr(boto3.session.Session, "client", lambda *_args, **_kwargs: sdk)
    storage = MediaSettings(
        data_dir=tmp_path,
        storage_backend="s3",
        s3_bucket="cache",
        derivative_cache_max_bytes=8,
        derivative_cache_ttl_seconds=60,
    ).media_storage
    now = datetime.now(UTC)
    prefix = {"Bucket": "cache", "Prefix": "derived/"}
    expired = {
        "Key": "derived/thumbnails/expired.jpg",
        "Size": 3,
        "LastModified": now - timedelta(seconds=90),
    }
    older = {
        "Key": "derived/video-previews/older.mp4",
        "Size": 5,
        "LastModified": now - timedelta(seconds=30),
    }
    newest = {"Key": "derived/thumbnails/newest.webp", "Size": 5, "LastModified": now}
    with Stubber(sdk) as s3:
        s3.add_response(
            "list_objects_v2",
            {"Contents": [expired], "IsTruncated": True, "NextContinuationToken": "page2"},
            prefix,
        )
        s3.add_response(
            "list_objects_v2",
            {"Contents": [newest, older]},
            {**prefix, "ContinuationToken": "page2"},
        )
        s3.add_response(
            "delete_objects",
            {},
            {
                "Bucket": "cache",
                "Delete": {
                    "Objects": [{"Key": item["Key"]} for item in [expired, older]],
                    "Quiet": True,
                },
            },
        )
        storage.prune_object_derivatives()
        s3.assert_no_pending_responses()
