"""读取管理员发布的工作机包。机器用安装时的公钥独立校验签名。"""

import hashlib
from pathlib import Path

from pydantic import ValidationError

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.schemas import DTO, WorkerDigest, WorkerRelease


class PublishedWorkerRelease(DTO):
    release: WorkerRelease
    public_key: WorkerDigest


def _worker_archive(settings: Settings, sha256: str) -> Path:
    return settings.data_dir / "worker-releases" / f"{sha256}.zip"


def published_worker(settings: Settings) -> PublishedWorkerRelease | None:
    path = settings.data_dir / "worker-releases" / "release.json"
    for _ in range(2):
        try:
            with path.open("rb") as source:
                content = source.read(8193)
            if len(content) > 8192:
                return None
            published = PublishedWorkerRelease.model_validate_json(content)
            release = published.release
            if _worker_archive(settings, release.sha256).stat().st_size == release.size:
                return published
        except FileNotFoundError:
            # 读完清单后，旧包可能刚被下一次发布移除。
            continue
        except (OSError, ValidationError):
            return None
        return None
    return None


def worker_archive_bytes(settings: Settings, release: WorkerRelease) -> bytes:
    """在响应前读完同一个发布包，发版移除文件时也不会中断已读出的下载。"""
    with _worker_archive(settings, release.sha256).open("rb") as source:
        content = source.read(release.size + 1)
    if len(content) != release.size or hashlib.sha256(content).hexdigest() != release.sha256:
        raise ValueError(msg("worker.theWorkMachinePackageDidNot"))
    return content


def published_worker_package(settings: Settings) -> tuple[PublishedWorkerRelease, bytes] | None:
    published = published_worker(settings)
    if published is None:
        return None
    try:
        return published, worker_archive_bytes(settings, published.release)
    except FileNotFoundError:
        replacement = published_worker(settings)
        if replacement is None:
            raise
        return replacement, worker_archive_bytes(settings, replacement.release)
