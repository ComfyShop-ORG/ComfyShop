"""将锁定的工作机包签名并发布到平台数据目录。私钥只在发布环境使用。"""

import argparse
from dataclasses import replace
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from filelock import FileLock

from comfyshop_worker.release import (
    BUILD_FILE,
    MAX_ARCHIVE_BYTES,
    Build,
    Release,
    package_entries,
    version_number,
)


def _read_package(package: Path) -> bytes:
    with package.open("rb") as source:
        data = source.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("工作机发布包过大")
    return data


def publish(package: Path, key_file: Path, destination: Path) -> Release:
    key = load_pem_private_key(key_file.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("工作机发布需要 Ed25519 私钥")
    data = _read_package(package)
    with ZipFile(BytesIO(data)) as archive:
        (build_file,) = [
            name for name in archive.namelist() if name.endswith(f"/comfyshop_worker/{BUILD_FILE}")
        ]
        if archive.getinfo(build_file).file_size > 4096:
            raise ValueError("工作机构建信息过大")
        build = Build.from_record(json.loads(archive.read(build_file)))
        package_entries(archive, build.version)
    release = Release(build, hashlib.sha256(data).hexdigest(), len(data), "")
    release = replace(release, signature=key.sign(release.signed_data()).hex())
    public_key = key.public_key().public_bytes_raw().hex()
    return _install(data, release, public_key, destination)


def install(source: Path, destination: Path) -> Release:
    record = json.loads((source / "release.json").read_bytes())
    release = Release.from_record(record["release"])
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(record["publicKey"]))
    try:
        public_key.verify(bytes.fromhex(release.signature), release.signed_data())
    except InvalidSignature as error:
        raise ValueError("工作机发布包签名无效") from error
    data = _read_package(source / f"{release.sha256}.zip")
    if len(data) != release.size or hashlib.sha256(data).hexdigest() != release.sha256:
        raise ValueError("工作机发布包校验失败")
    return _install(data, release, public_key.public_bytes_raw().hex(), destination)


def _install(data: bytes, release: Release, public_key: str, destination: Path) -> Release:
    destination.mkdir(parents=True, exist_ok=True)
    with FileLock(str(destination / ".publish.lock")):
        _publish_files(data, release, public_key, destination)
    return release


def _publish_files(data: bytes, release: Release, public_key: str, destination: Path) -> None:
    manifest = destination / "release.json"
    if manifest.is_file():
        previous = json.loads(manifest.read_bytes())
        old = Release.from_record(previous["release"])
        if previous["publicKey"] != public_key:
            raise ValueError("发布目录已绑定其他公钥")
        if old != release and version_number(old.build.version) >= version_number(
            release.build.version
        ):
            raise ValueError("不同内容必须发布为更高的工作机版本")
    archive_path = destination / f"{release.sha256}.zip"
    with TemporaryDirectory(dir=destination) as stage:
        scratch = Path(stage)
        if archive_path.exists():
            if archive_path.read_bytes() != data:
                raise ValueError("发布目录中已有同名但内容不同的包")
        else:
            archive = scratch / archive_path.name
            archive.write_bytes(data)
            archive.replace(archive_path)
        record = {
            "release": release.payload() | {"signature": release.signature},
            "publicKey": public_key,
        }
        staged = scratch / manifest.name
        staged.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        staged.replace(manifest)
    for previous_archive in destination.glob("*.zip"):
        if (
            previous_archive != archive_path
            and re.fullmatch(r"[0-9a-f]{64}\.zip", previous_archive.name)
            and previous_archive.is_file()
        ):
            try:
                previous_archive.unlink(missing_ok=True)
            except OSError as error:
                raise OSError(
                    f"新版已生效。无法清理旧包 {previous_archive.name}，可重试发布。"
                ) from error


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--key", type=Path, help="对启动包签名所用的 Ed25519 私钥")
    mode.add_argument("--install-from", type=Path, help="包含独立签名包和发布清单的目录")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.install_from:
            if args.package:
                parser.error("--install-from 与 --package 不能同时使用")
            signed = install(args.install_from, args.destination)
        else:
            package = args.package or Path("dist/downloads/comfyshop-worker.zip")
            signed = publish(package, args.key, args.destination)
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as error:
        parser.exit(1, f"发布命令未完成。{error}\n")
    print(f"已发布工作机 {signed.build.version}（{signed.sha256}）")
