"""工作机版本与发布包签名。签名使用固定字段，安装时再核对包内构建标识。"""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import stat
import tomllib
from typing import TYPE_CHECKING, Self
from zipfile import ZipFile, ZipInfo

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PROTOCOL_VERSION = 3
BUILD_FILE = "worker-build.json"
UPDATE_KEY_FILE = "worker-release.pub"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
_VERSION = re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.(?:0|[1-9][0-9]{0,5})){2}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


def version_number(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError("无效的工作机版本")
    return tuple(map(int, value.split(".")))


def package_entries(archive: ZipFile, version: str) -> dict[str, ZipInfo]:
    """验证发布物仅含程序文件，返回解压时使用的相对路径。"""
    prefix = f"comfyshop-worker-{version}/"
    metadata = f"comfyshop_worker/{BUILD_FILE}"
    required = {"requirements.txt", "comfyshop_worker/__main__.py", metadata}
    allowed = {
        "requirements.txt",
        "pyproject.toml",
        "README.md",
        "start.cmd",
        "start.sh",
        "start.command",
        metadata,
    }
    files = {}
    size = 0
    for entry in archive.infolist():
        name = entry.filename.removeprefix(prefix)
        size += entry.file_size
        if (
            not entry.filename.startswith(prefix)
            or not (name in allowed or re.fullmatch(r"comfyshop_worker/[a-z0-9_]+\.py", name))
            or name in files
            or stat.S_ISLNK(entry.external_attr >> 16)
            or size > MAX_ARCHIVE_BYTES * 2
        ):
            raise ValueError("更新包目录无效")
        files[name] = entry
    if not required <= files.keys():
        raise ValueError("更新包缺少必要文件")
    return files


@dataclass(frozen=True)
class Build:
    version: str
    build: str | None = None

    @classmethod
    def from_record(cls, record: dict) -> Self:
        number, build = record["version"], record["build"]
        version_number(number)
        if not isinstance(build, str) or not _DIGEST.fullmatch(build):
            raise ValueError("无效的工作机构建标识")
        return cls(number, build)

    @classmethod
    def installed(cls, source: Path) -> Self | None:
        packaged = source / "comfyshop_worker" / BUILD_FILE
        if packaged.is_file():
            return cls.from_record(json.loads(packaged.read_bytes()))
        project = source / "pyproject.toml"
        if project.is_file():
            package = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {})
            if package.get("name") == "comfyshop-worker":
                return cls(package["version"])
        try:
            return cls(version("comfyshop-worker"))
        except PackageNotFoundError:
            return None


@dataclass(frozen=True)
class Release:
    build: Build
    sha256: str
    size: int
    signature: str

    @classmethod
    def from_record(cls, record: dict) -> Self:
        build = Build.from_record(record)
        checksum, size, signature = record["sha256"], record["size"], record["signature"]
        if (
            not isinstance(checksum, str)
            or not _DIGEST.fullmatch(checksum)
            or type(size) is not int
            or not 0 < size <= MAX_ARCHIVE_BYTES
            or not isinstance(signature, str)
            or not re.fullmatch(r"[0-9a-f]{128}", signature)
        ):
            raise ValueError("无效的工作机发布包信息")
        if record["protocolVersion"] != PROTOCOL_VERSION:
            raise ValueError("发布包要求不同的工作机协议")
        return cls(build, checksum, size, signature)

    def payload(self) -> dict:
        return {
            "version": self.build.version,
            "build": self.build.build,
            "protocolVersion": PROTOCOL_VERSION,
            "sha256": self.sha256,
            "size": self.size,
        }

    def signed_data(self) -> bytes:
        payload = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return b"ComfyShop worker release v1\n" + payload.encode("ascii")

    def verify(self, key: "Ed25519PublicKey", installed: Build) -> None:
        key.verify(bytes.fromhex(self.signature), self.signed_data())
        if version_number(self.build.version) <= version_number(installed.version):
            raise ValueError("发布包版本必须高于当前运行版本")
