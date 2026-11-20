"""本地和 S3 兼容存储，管理原件、暂存目录和可重建的派生缓存。"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from errno import EXDEV
from hashlib import file_digest, sha256
from os import fstat, link, stat_result, utime
from pathlib import Path
from shutil import copyfileobj
from stat import S_ISREG
from time import time
from typing import TYPE_CHECKING

from boto3.session import Session
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from comfyshop_media.errors import MediaError
from comfyshop_media.staging import StagingDirectory, prune_staging

if TYPE_CHECKING:
    from botocore.response import StreamingBody
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import GetObjectRequestTypeDef, PutObjectRequestTypeDef

    from comfyshop_media.settings import MediaSettings

_NOT_FOUND = {"NoSuchKey", "NotFound", "404"}
_ORIGINAL_PREFIX = "originals"
_PUBLICATION_STAGING = ".comfyshop-publish"


def original_key(name: str) -> str:
    if name in {"", ".", ".."} or Path(name).name != name or "\\" in name:
        raise ValueError("媒体存储名无效")
    return f"{_ORIGINAL_PREFIX}/{name}"


class StorageError(OSError):
    """媒体存储暂时不可用。"""


@dataclass(frozen=True)
class ObjectRead:
    body: StreamingBody
    size: int
    etag: str
    last_modified: datetime
    content_range: str | None


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        link(source, target)
    except OSError as error:
        if error.errno != EXDEV:
            raise
        # 导入或单独挂载子目录时，仍在最终路径所在的文件系统内原子发布。
        with StagingDirectory(target.parent / _PUBLICATION_STAGING) as directory:
            temporary = Path(directory) / "original"
            with source.open("rb") as original, temporary.open("xb") as output:
                copyfileobj(original, output, length=1024 * 1024)
            info = source.stat()
            utime(temporary, (info.st_atime, info.st_mtime))
            link(temporary, target)


def _evictions[T](entries: list[tuple[float, int, T]], cutoff: float, budget: int) -> list[T]:
    remaining = sum(size for _, size, _ in entries)
    remove = []
    for modified, size, key in sorted(entries, key=lambda entry: entry[0]):
        if modified > cutoff and remaining <= budget:
            break
        remove.append(key)
        remaining -= size
    return remove


def _read_error(error: ClientError) -> MediaError | StorageError:
    code = error.response.get("Error", {}).get("Code")
    if code in _NOT_FOUND:
        return MediaError("missing", "媒体原文件不存在")
    if code in {"InvalidRange", "416"}:
        return MediaError("range", "Range 超出文件范围")
    if code == "InvalidArgument":
        return MediaError("range_syntax", "Range 请求无效")
    return StorageError("读取对象存储失败")


class MediaStorage:
    def __init__(self, settings: MediaSettings) -> None:
        self._data_dir = settings.data_dir
        self._cache_max_bytes = settings.derivative_cache_max_bytes
        self._cache_ttl = settings.derivative_cache_ttl_seconds
        self._cache_directories = (settings.thumbnail_dir, settings.video_preview_dir)
        self._bucket = settings.s3_bucket or ""
        self._s3: S3Client | None = None
        if settings.storage_backend == "s3":
            try:
                # 不在并发请求中使用 boto3 的全局默认会话。
                self._s3 = Session().client(
                    "s3",
                    endpoint_url=settings.s3_endpoint_url,
                    region_name=settings.s3_region,
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=(
                        settings.s3_secret_access_key.get_secret_value()
                        if settings.s3_secret_access_key
                        else None
                    ),
                    config=Config(
                        s3={"addressing_style": settings.s3_addressing_style},
                        connect_timeout=5,
                        read_timeout=30,
                        max_pool_connections=32,
                        retries={"mode": "standard", "total_max_attempts": 3},
                        request_checksum_calculation="when_required",
                        response_checksum_validation="when_required",
                    ),
                )
            except BotoCoreError as error:
                raise StorageError("无法初始化对象存储客户端") from error

    def staging_directory(self) -> StagingDirectory:
        return StagingDirectory(self._data_dir / "staging")

    def prune_abandoned_staging(self, recover: Callable[[Path], None] | None = None) -> None:
        prune_staging(self._data_dir / "staging", recover)
        prune_staging(self._data_dir / _ORIGINAL_PREFIX / _PUBLICATION_STAGING, None)
        for directory in self._cache_directories:
            prune_staging(directory / _PUBLICATION_STAGING, None)

    def put(self, name: str, source: Path, content_type: str) -> None:
        """写入已验证的内容，保留原有存储名。恢复时以独占方式创建目标。"""
        key = original_key(name)
        if self._s3 is None:
            path = self._data_dir / key
            if source != path:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                _link_or_copy(source, path)
            return
        self._put_object(key, source, content_type)

    def _put_object(
        self, key: str, source: Path, content_type: str, *, replace: bool = False
    ) -> None:
        assert self._s3 is not None
        try:
            with source.open("rb") as body:
                params: PutObjectRequestTypeDef = {
                    "Bucket": self._bucket,
                    "Key": key,
                    "Body": body,
                    "ContentLength": source.stat().st_size,
                    "ContentType": content_type,
                }
                if not replace:
                    params["IfNoneMatch"] = "*"
                self._s3.put_object(**params)
        except (ClientError, BotoCoreError) as error:
            raise StorageError("写入对象存储失败") from error

    def _derivative_key(self, path: Path) -> str:
        return f"derived/{path.relative_to(self._data_dir).as_posix()}"

    def _cache_entry_is_current(self, size: int, modified: float) -> bool:
        return 0 < size <= self._cache_max_bytes and modified > time() - self._cache_ttl

    def derivative_is_current(self, info: stat_result) -> bool:
        return self._cache_entry_is_current(info.st_size, info.st_mtime)

    def _publish_derivative(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        def publish(directory: str) -> None:
            temporary = Path(directory) / "derived"
            _link_or_copy(source, temporary)
            temporary.replace(target)

        try:
            with self.staging_directory() as directory:
                publish(directory)
        except OSError as error:
            if error.errno != EXDEV:
                raise
            with StagingDirectory(target.parent / _PUBLICATION_STAGING) as directory:
                publish(directory)

    def reuse_derivative(self, target: Path, output: Path) -> bool:
        """固定已缓存的派生文件，清理原缓存路径时仍能读取。"""
        try:
            if self.derivative_is_current(target.stat()):
                _link_or_copy(target, output)
                return True
        except FileNotFoundError:
            pass
        return False

    def restore_derivative(self, target: Path) -> bool:
        """把已生成的 S3 派生文件放回应用卷，命中时避免重新处理原文件。"""
        if self._s3 is None or not self._cache_max_bytes:
            return False
        try:
            result = self._s3.get_object(Bucket=self._bucket, Key=self._derivative_key(target))
            with closing(result["Body"]) as body:
                modified = result["LastModified"].timestamp()
                if not self._cache_entry_is_current(result["ContentLength"], modified):
                    return False
                with self.staging_directory() as directory:
                    temporary = Path(directory) / "download"
                    with temporary.open("xb") as output:
                        copyfileobj(body, output, length=1024 * 1024)
                    utime(temporary, (modified, modified))
                    self._publish_derivative(temporary, target)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _NOT_FOUND:
                return False
            raise StorageError("读取对象存储派生文件失败") from error
        except BotoCoreError as error:
            raise StorageError("读取对象存储派生文件失败") from error
        return True

    def persist_derivative(self, source: Path, target: Path, content_type: str) -> None:
        """每个派生文件键对应固定的原件内容和处理参数，可被其他实例复用。"""
        if not self.derivative_is_current(source.stat()):
            return
        self._publish_derivative(source, target)
        if self._s3 is not None:
            self._put_object(self._derivative_key(target), source, content_type, replace=True)

    def prune_local_derivatives(self) -> None:
        cutoff = time() - self._cache_ttl
        entries: list[tuple[float, int, Path]] = []
        for directory in self._cache_directories:
            for path in directory.glob("*"):
                if path.suffix not in {".webp", ".jpg", ".mp4"}:
                    continue
                try:
                    info = path.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if S_ISREG(info.st_mode):
                    entries.append((info.st_mtime, info.st_size, path))
        for path in _evictions(entries, cutoff, self._cache_max_bytes):
            path.unlink(missing_ok=True)

    def prune_object_derivatives(self) -> None:
        if self._s3 is None:
            return
        cutoff = time() - self._cache_ttl
        try:
            pages = self._s3.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix="derived/"
            )
            entries = [
                (modified.timestamp(), size, key)
                for page in pages
                for item in page.get("Contents", [])
                if (modified := item.get("LastModified")) is not None
                and (size := item.get("Size")) is not None
                and (key := item.get("Key")) is not None
            ]
            keys = _evictions(entries, cutoff, self._cache_max_bytes)
            for offset in range(0, len(keys), 1000):
                result = self._s3.delete_objects(
                    Bucket=self._bucket,
                    Delete={
                        "Objects": [{"Key": key} for key in keys[offset : offset + 1000]],
                        "Quiet": True,
                    },
                )
                if result.get("Errors"):
                    raise StorageError("部分对象存储派生文件清理失败")
        except (ClientError, BotoCoreError) as error:
            raise StorageError("清理对象存储派生文件失败") from error

    def delete(self, name: str) -> None:
        key = original_key(name)
        if self._s3 is None:
            (self._data_dir / key).unlink(missing_ok=True)
            return
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise StorageError("删除对象存储文件失败") from error

    def open_original(self, name: str, byte_range: str | None = None) -> ObjectRead:
        """打开 S3 原件字节流，调用方读完或中断后关闭 body。"""
        assert self._s3 is not None
        params: GetObjectRequestTypeDef = {"Bucket": self._bucket, "Key": original_key(name)}
        if byte_range:
            params["Range"] = byte_range
        try:
            result = self._s3.get_object(**params)
        except ClientError as error:
            raise _read_error(error) from error
        except BotoCoreError as error:
            raise StorageError("读取对象存储失败") from error
        return ObjectRead(
            result["Body"],
            result["ContentLength"],
            result["ETag"],
            result["LastModified"],
            result.get("ContentRange"),
        )

    def original_validators(self, name: str) -> tuple[str, datetime]:
        assert self._s3 is not None
        try:
            metadata = self._s3.head_object(Bucket=self._bucket, Key=original_key(name))
        except ClientError as error:
            raise _read_error(error) from error
        except BotoCoreError as error:
            raise StorageError("读取对象存储失败") from error
        return metadata["ETag"], metadata["LastModified"]

    def original_path(self, name: str) -> Path | None:
        """返回本地原件路径，S3 模式使用对象流读取。"""
        if self._s3 is not None:
            return None
        path = self._data_dir / original_key(name)
        if not path.is_file():
            raise MediaError("missing", "媒体原文件不存在")
        return path

    def original_matches(self, name: str, size: int, expected_sha256: str) -> bool:
        """流式核对原件大小和 SHA-256。缺失或内容不符返回 False，读取故障交给调用方。"""
        try:
            if (path := self.original_path(name)) is not None:
                with path.open("rb") as file:
                    return (
                        fstat(file.fileno()).st_size == size
                        and file_digest(file, "sha256").hexdigest() == expected_sha256
                    )
            original = self.open_original(name)
            with closing(original.body) as body:
                if original.size != size:
                    return False
                digest = sha256()
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    digest.update(chunk)
                return digest.hexdigest() == expected_sha256
        except FileNotFoundError:
            return False
        except MediaError as error:
            if error.kind == "missing":
                return False
            raise
        except BotoCoreError as error:
            raise StorageError("读取对象存储失败") from error

    @contextmanager
    def local_original(self, name: str) -> Iterator[Path]:
        """需要文件路径的转码工具读取临时副本。"""
        if (path := self.original_path(name)) is not None:
            yield path
            return
        with self.staging_directory() as directory:
            path = Path(directory) / "original"
            try:
                with closing(self.open_original(name).body) as body, path.open("xb") as output:
                    copyfileobj(body, output, length=1024 * 1024)
            except BotoCoreError as error:
                raise StorageError("读取对象存储失败") from error
            yield path

    def ensure_empty(self) -> None:
        """导入只允许写入空的原文件目录或空的专用存储桶。"""
        self.restore_inventory(())

    def _local_original_keys(self) -> Iterator[str]:
        directory = self._data_dir / _ORIGINAL_PREFIX
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError("目标原件目录无效")
        if not directory.is_dir():
            return
        for path in directory.iterdir():
            if path.name == _PUBLICATION_STAGING and path.is_dir() and not path.is_symlink():
                prune_staging(path, None)
                if all(
                    p.name == ".allocation.lock" and p.is_file() and not p.is_symlink()
                    for p in path.iterdir()
                ):
                    continue
            if path.is_symlink() or not path.is_file():
                raise ValueError("目标原件目录包含无效文件")
            yield f"{_ORIGINAL_PREFIX}/{path.name}"

    def restore_inventory(self, names: Collection[str]) -> set[str]:
        """返回可核对并复用的备份原件名。目标含其他文件时拒绝导入。"""
        expected = {original_key(name): name for name in names}
        if self._s3 is None:
            keys = self._local_original_keys()
        else:
            pages = self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket)
            keys = (item.get("Key", "") for page in pages for item in page.get("Contents", []))
        found = set()
        for key in keys:
            if key not in expected:
                raise ValueError("目标存储包含备份清单以外的文件")
            found.add(expected[key])
        return found

    def check_bucket(self) -> None:
        if self._s3 is None:
            raise ValueError("检查存储桶需要启用 S3 存储")
        self._s3.head_bucket(Bucket=self._bucket)

    def create_bucket(self) -> None:
        """只供本地 RustFS 的 Compose 初始化服务调用。"""
        try:
            self.check_bucket()
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in _NOT_FOUND | {"NoSuchBucket"}:
                raise
            assert self._s3 is not None
            self._s3.create_bucket(Bucket=self._bucket)
