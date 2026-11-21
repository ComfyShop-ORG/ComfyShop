"""在原安装目录外准备发布包，由启动器验证新版就绪后切换。"""

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from filelock import FileLock
import httpx

from .config import Config, write_json
from .platform import Platform, PlatformError
from .release import Build, Release, package_entries, version_number
from .update_control import CONTROL_ENV, STARTUP_SECONDS, UPDATE_EXIT, UpdateControl

log = logging.getLogger("comfyshop")


class UpdateError(Exception):
    """可回报到工作机页面的更新失败原因。"""


def _extract(archive: Path, destination: Path, release: Release) -> None:
    with ZipFile(archive) as bundle:
        for name, entry in package_entries(bundle, release.build.version).items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    if Build.installed(destination) != release.build:
        raise ValueError("更新包与发布的版本不一致")


def _python(source: Path) -> Path:
    return source / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")


async def _stop(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            if process.returncode is None:
                process.kill()
            await process.wait()


async def _run_install(*command: str, source: Path) -> None:
    process = await asyncio.create_subprocess_exec(*command, cwd=source)
    try:
        if await asyncio.wait_for(process.wait(), 300):
            raise UpdateError("新版依赖安装失败")
    finally:
        await _stop(process)


class Launcher:
    def __init__(self, config: Config, bootstrap: Path, key: Ed25519PublicKey, uv: str):
        self.config = config
        self.bootstrap = bootstrap
        self.key = key
        self.key_id = key.public_bytes_raw().hex()
        self.uv = uv
        self.directory = config.state_dir.resolve() / "updates"
        self.versions = self.directory / "versions"
        self.current = self.directory / "current.json"
        self.platform = Platform(config.server_url, config.api_key)
        self.environment = os.environ | {
            "COMFYSHOP_WORKER_STATE_DIR": str(config.state_dir.resolve())
        }
        if file := self.environment.get("COMFYSHOP_WORKER_CONFIG"):
            self.environment["COMFYSHOP_WORKER_CONFIG"] = str(Path(file).resolve())

    def installed(self) -> Path:
        if not self.current.is_file():
            return self.bootstrap
        record = json.loads(self.current.read_bytes())
        if record.get("publicKey") != self.key_id:
            return self.bootstrap
        sha256 = record["sha256"]
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise UpdateError("无法读取当前安装的工作机版本")
        installed = self.versions / sha256
        build = Build.installed(installed) if installed.is_dir() else None
        bootstrap = Build.installed(self.bootstrap)
        if (
            build
            and bootstrap
            and version_number(build.version) >= version_number(bootstrap.version)
        ):
            return installed
        return self.bootstrap

    async def prepare(self, update_id: str, installed: Path) -> Path:
        try:
            record = await self.platform.request(f"updates/{update_id}", method="PUT")
            if not isinstance(record, dict):
                raise ValueError("平台返回的发布信息无效")
            release = Release.from_record(record)
            build = Build.installed(installed)
            if build is None:
                raise ValueError("当前工作机版本未知")
            release.verify(self.key, build)
        except (KeyError, TypeError, ValueError, InvalidSignature) as error:
            raise UpdateError("发布包签名或版本校验失败") from error
        directory = self.versions / release.sha256
        with TemporaryDirectory(dir=self.directory) as temporary:
            archive = Path(temporary) / "package.zip"
            async with asyncio.timeout(120):
                await self.platform.download_verified(
                    f"releases/{release.sha256}", archive, release.size, release.sha256
                )
            staged = Path(temporary) / "program"
            try:
                _extract(archive, staged, release)
            except (KeyError, TypeError, ValueError, BadZipFile) as error:
                raise UpdateError("更新包内容校验失败") from error
            if directory.exists():
                shutil.rmtree(directory)
            staged.replace(directory)
        await _run_install(
            self.uv, "--no-config", "venv", "--python", "3.12", ".venv", source=directory
        )
        await _run_install(
            self.uv,
            "--no-config",
            "pip",
            "sync",
            "--python",
            str(_python(directory)),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "requirements.txt",
            source=directory,
        )
        return directory

    async def run_child(
        self, source: Path, *, trial: bool = False, once: bool = False
    ) -> tuple[int, str | None]:
        with TemporaryDirectory(dir=self.directory) as temporary:
            control_path = Path(temporary)
            if trial:
                (control_path / "trial").write_text(source.name, encoding="ascii")
            control = UpdateControl(control_path)
            process = await asyncio.create_subprocess_exec(
                str(_python(source)) if source != self.bootstrap else sys.executable,
                "-m",
                "comfyshop_worker",
                *(["--once"] if once else []),
                cwd=source,
                env=self.environment | {CONTROL_ENV: temporary},
            )
            try:
                if trial:
                    async with asyncio.timeout(STARTUP_SECONDS):
                        while not control.ready.is_file() and process.returncode is None:
                            await asyncio.sleep(0.1)
                    if process.returncode is not None:
                        raise UpdateError("新版未能启动")
                    write_json(self.current, {"sha256": source.name, "publicKey": self.key_id})
                status = await process.wait()
                request = (
                    json.loads(control.request.read_bytes())
                    if status == UPDATE_EXIT and control.request.is_file()
                    else None
                )
                return status, str(UUID(request["id"])) if request else None
            finally:
                await _stop(process)

    def fail(self, update_id: str, error: Exception) -> None:
        reason = str(error) if isinstance(error, UpdateError) else "下载、安装或连接检查失败"
        log.warning("%s，继续使用原工作机版本", reason)
        write_json(self.directory / "failure.json", {"id": update_id, "reason": reason})

    async def run(self, *, once: bool = False) -> int:
        self.versions.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            with FileLock(str(self.directory / "launcher.lock"), timeout=0):
                installed = self.installed()
                result, update_id = await self.run_child(installed, once=once)
                while update_id:
                    try:
                        candidate = await self.prepare(update_id, installed)
                        result, next_update = await self.run_child(candidate, trial=True)
                    except (
                        UpdateError,
                        PlatformError,
                        httpx.TransportError,
                        OSError,
                        TimeoutError,
                    ) as error:
                        # 目录切换只在就绪后生效。旧进程回到主循环时会用心跳回报失败。
                        self.fail(update_id, error)
                        result, update_id = await self.run_child(installed)
                    else:
                        installed = candidate
                        update_id = next_update
                return result
        finally:
            await self.platform.close()
