"""Run downloaded ComfyShop startup packages on a test host."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
import tomllib
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

LAUNCHERS = {
    "Windows": ["cmd.exe", "/d", "/c", "call", "start.cmd"],
    "Darwin": ["/bin/sh", "./start.command"],
    "Linux": ["/bin/sh", "./start.sh"],
}


class WindowsJob:
    """Own the launcher and its descendants under the runner's restricted token."""

    def __init__(self):
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_longlong),
                ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD),
                ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t),
                ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits),
                ("io_counters", ctypes.c_ulonglong * 6),
                ("memory_limits", ctypes.c_size_t * 4),
            ]

        self.kernel = kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, pid):
        process = self.kernel.OpenProcess(0x0100 | 0x0001, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(process)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def spawn_worker(launcher, *, cwd, output, env):
    options = {"cwd": cwd, "stdout": output, "stderr": subprocess.STDOUT, "env": env}
    if os.name != "nt":
        return subprocess.Popen(
            launcher, stdin=subprocess.DEVNULL, start_new_session=True, **options
        ), None
    job = WindowsJob()
    try:
        # Wait for job assignment before the wrapper can launch cmd.exe and its descendants.
        gate = (
            "import subprocess, sys\n"
            "if sys.stdin.buffer.read(1) != b'1': sys.exit(1)\n"
            "sys.exit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL))\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", gate, *launcher], stdin=subprocess.PIPE, **options
        )
        with process.stdin:
            job.assign(process.pid)
            process.stdin.write(b"1")
    except BaseException:
        job.close()
        raise
    return process, job


def exchange(url, payload=None):
    address = urlsplit(url)
    if address.scheme not in ("http", "https") or not address.hostname or address.username:
        raise ValueError("Expected a test HTTP origin")
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"})  # noqa: S310
    with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Test response exceeds 8 MiB")
    return data


def extract_bundle(bundle, directory):
    with ZipFile(bundle) as archive:
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            if not path.parts or path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe worker package path")
            if "\\" in entry.filename or ":" in entry.filename:
                raise ValueError("Unsafe worker package path")
        if sum(entry.file_size for entry in archive.infolist()) > 32 * 1024 * 1024:
            raise ValueError("Expanded worker package exceeds 32 MiB")
        archive.extractall(directory)
    (config,) = directory.glob("*/worker.json")
    return config


def worker_folder(root, command):
    edition, role = command["edition"], command["role"]
    if edition not in ("team", "sqlite") or role not in ("publisher", "reader"):
        raise ValueError("Unknown edition or worker role")
    run_id = command["runId"]
    if not re.fullmatch(r"[a-z0-9-]{1,48}", run_id):
        raise ValueError("Invalid test run ID")
    return root / run_id / edition / role


def start_worker(root, command):
    folder = worker_folder(root, command)
    folder.mkdir(parents=True, mode=0o700)
    package = folder / "worker.zip"
    binary = exchange(command["site"] + "/api/v1/worker/package")
    digest = hashlib.sha256(binary).hexdigest()
    if digest != command["sha256"]:
        raise ValueError("Download SHA-256 differs from the test site's package")
    package.write_bytes(binary)
    config = extract_bundle(package, folder)
    values = json.loads(config.read_text(encoding="utf-8"))
    if values.get("serverUrl") != command["site"] or values.get("apiKey"):
        raise ValueError("Unexpected serverUrl or preconfigured key in worker package")
    if (key := command.get("publicKey")) and (
        config.with_name("worker-release.pub").read_text(encoding="ascii").strip() != key
    ):
        raise ValueError("The starter contains a different release verification key")
    values.update(comfyUrl=command["comfy"], stateDir=str(folder / "state"))
    config.write_text(json.dumps(values), encoding="utf-8")
    config.chmod(0o600)
    project = tomllib.loads((config.parent / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    build_file = config.parent / "comfyshop_worker/worker-build.json"
    identity = json.loads(build_file.read_bytes()) if build_file.is_file() else None
    if identity is not None and identity["version"] != version:
        raise ValueError("Worker build metadata differs from the package version")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("COMFYSHOP_")
    }
    temporary = root / "tmp"
    temporary.mkdir(exist_ok=True)
    environment.update(
        UV_CACHE_DIR=str(root / "uv-cache"),
        UV_PYTHON_INSTALL_DIR=str(root / "python"),
        TMPDIR=str(temporary),
        TMP=str(temporary),
        TEMP=str(temporary),
        SSH_TTY="comfyshop-e2e",
        PYTHONUNBUFFERED="1",
    )
    hosts = [urlsplit(command[key]).hostname for key in ("site", "comfy")]
    bypass = ",".join(host for host in hosts if host)
    for key in ("NO_PROXY", "no_proxy"):
        environment[key] = ",".join(filter(None, (environment.get(key), bypass)))
    launcher = LAUNCHERS[platform.system()]
    log = folder / "worker.log"
    with log.open("wb") as output:
        process, job = spawn_worker(launcher, cwd=config.parent, output=output, env=environment)
    report = {
        "path": str(folder),
        "launcher": launcher[-1].removeprefix("./"),
        "version": version,
        "serverUrl": values["serverUrl"],
        "sha256": digest,
    }
    if identity is not None:
        report["build"] = identity["build"]
    return process, job, log, report


def installed_update(root, command):
    directory = worker_folder(root, command) / "state" / "updates"
    marker = directory / "current.json"
    if not marker.is_file():
        return {"current": None}
    current = json.loads(marker.read_bytes())
    if not re.fullmatch(r"[a-f0-9]{64}", current["sha256"]):
        raise ValueError("Invalid installed release digest")
    build = directory / "versions" / current["sha256"] / "comfyshop_worker/worker-build.json"
    return {"current": current, "build": json.loads(build.read_bytes())}


def pairing_code(process, log):
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Startup exited with status {process.returncode}; log: {log}")
        match = re.search(r"/machines/link\?code=([A-Z0-9]+)", log.read_text(errors="replace"))
        if match:
            return match[1]
        time.sleep(0.5)
    raise TimeoutError(f"No pairing request; log: {log}")


def stop_workers(workers):
    for process, job in workers:
        if job:
            job.close()
            process.wait(timeout=8)
            continue
        if process.poll() is not None:
            continue
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=8)
    workers.clear()


def inventory(root):
    rows = []
    for child in sorted(root.iterdir()):
        paths = child.rglob("*") if child.is_dir() else [child]
        size = sum(
            path.stat().st_size for path in paths if not path.is_symlink() and path.is_file()
        )
        rows.append({"path": str(child), "bytes": size})
    return rows


def run_agent(ticket, root):
    root = root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    workers = []
    exchange(
        ticket + "/host",
        {
            "os": platform.system(),
            "arch": platform.machine(),
            "release": platform.release(),
            "root": str(root),
        },
    )
    previous = 0
    try:
        while True:
            command = json.loads(exchange(ticket))
            if not command or command["seq"] == previous:
                time.sleep(0.5)
                continue
            previous = command["seq"]
            try:
                if command["action"] in ("stop", "finish"):
                    stop_workers(workers)
                    report = {"storage": inventory(root), "stopped": True}
                elif command["action"] == "start":
                    process, job, log, report = start_worker(root, command)
                    workers.append((process, job))
                    report["pairingCode"] = pairing_code(process, log)
                elif command["action"] == "installed-update":
                    report = installed_update(root, command)
                else:
                    raise ValueError("Unknown native test action")
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                report = {"error": str(error)}
            exchange(ticket + "/report", {"seq": previous, **report})
            if command["action"] == "finish":
                return
    finally:
        stop_workers(workers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket", help="Test controller's private session URL")
    parser.add_argument("root", type=Path, help="Dedicated storage root on this host")
    args = parser.parse_args()
    run_agent(args.ticket, args.root)
