"""Register the standalone entry point with the current user's service manager."""

import getpass
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

SERVICE_ACTIONS = ("install", "start", "stop", "status", "remove")
LOG_DIRECTORY_ENV = "COMFYSHOP_BACKGROUND_LOG_DIR"


class ServiceError(ValueError):
    pass


@dataclass(frozen=True)
class ServiceLaunch:
    source: Path
    command: list[str]


def service_name(config: Path) -> str:
    identity = hashlib.sha256(os.path.normcase(str(config)).encode()).hexdigest()[:12]
    return f"comfyshop-worker-{identity}"


def service_launch(config: Path, source: Path, state: Path, uv: str | None) -> ServiceLaunch:
    executable = Path(sys.executable).absolute()
    if sys.platform == "win32" and executable.with_name("pythonw.exe").is_file():
        executable = executable.with_name("pythonw.exe")
    command = [
        str(executable),
        "-m",
        "comfyshop_worker",
        "--service-run",
        str(config),
        "--service-logs",
        str(state.resolve()),
    ]
    if uv:
        command.extend(["--launcher-uv", uv])
    return ServiceLaunch(source, command)


def launch_agent(name: str, launch: ServiceLaunch) -> bytes:
    return plistlib.dumps(
        {
            "Label": name,
            "ProgramArguments": launch.command,
            "WorkingDirectory": str(launch.source),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 5,
        }
    )


def _unit_arg(value: str) -> str:
    return json.dumps(value.replace("%", "%%"), ensure_ascii=False)


def systemd_unit(launch: ServiceLaunch) -> bytes:
    directory = str(launch.source)
    # WorkingDirectory takes one unquoted path. A newline would start a new setting.
    if "\n" in directory or "\r" in directory:
        raise ServiceError("后台工作机目录不能包含换行")
    command = " ".join(_unit_arg(arg.replace("$", "$$")) for arg in launch.command)
    return (
        "[Unit]\nDescription=ComfyShop work machine\n\n"
        "[Service]\n"
        f"WorkingDirectory={directory.replace('%', '%%')}\n"
        f"ExecStart={command}\n"
        "Restart=on-failure\nRestartSec=5s\n\n"
        "[Install]\nWantedBy=default.target\n"
    ).encode()


def scheduled_task(launch: ServiceLaunch, user: str) -> bytes:
    executable, *arguments = launch.command
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><UserId>{escape(user)}</UserId></LogonTrigger></Triggers>
  <Principals><Principal id="Worker">
    <UserId>{escape(user)}</UserId><LogonType>InteractiveToken</LogonType>
    <RunLevel>LeastPrivilege</RunLevel>
  </Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <RestartOnFailure><Interval>PT1M</Interval><Count>10</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Worker"><Exec>
    <Command>{escape(executable)}</Command>
    <Arguments>{escape(subprocess.list2cmdline(arguments))}</Arguments>
    <WorkingDirectory>{escape(str(launch.source))}</WorkingDirectory>
  </Exec></Actions>
</Task>
""".encode("utf-16")


def _run(command: list[str], *, check: bool = True, quiet: bool = False) -> int:
    return subprocess.run(
        command,
        check=check,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    ).returncode


def _write_registration(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as temp:
        pending = Path(temp) / path.name
        pending.write_bytes(data)
        pending.chmod(0o600)
        pending.replace(path)


def _mac_service(action: str, name: str, launch: ServiceLaunch | None) -> int:
    domain = f"gui/{os.getuid()}"
    target = f"{domain}/{name}"
    path = Path.home() / "Library" / "LaunchAgents" / f"{name}.plist"
    probe = ["launchctl", "print", target]
    loaded = _run(probe, check=False, quiet=True) == 0
    if action == "status":
        print("工作机后台服务已载入" if loaded else "工作机后台服务未载入")
        return 0 if loaded else 1
    if action in {"install", "stop", "remove"} and loaded:
        _run(["launchctl", "bootout", target])
        deadline = time.monotonic() + 10
        while _run(probe, check=False, quiet=True) == 0:
            if time.monotonic() >= deadline:
                raise ServiceError("后台工作机仍在停止，请稍后重试")
            time.sleep(0.1)
        loaded = False
    if action == "remove":
        path.unlink(missing_ok=True)
    if launch:
        _write_registration(path, launch_agent(name, launch))
    if action in {"install", "start"}:
        if not path.is_file():
            raise ServiceError("请先安装工作机后台服务")
        if not loaded:
            _run(["launchctl", "bootstrap", domain, str(path)])
        elif action == "start":
            _run(["launchctl", "kickstart", target])
    return 0


def _linux_service(action: str, name: str, launch: ServiceLaunch | None) -> int:
    unit = f"{name}.service"
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = config_home / "systemd" / "user" / unit
    base = ["systemctl", "--user"]
    if launch:
        _write_registration(path, systemd_unit(launch))
        _run([*base, "daemon-reload"])
        return _run([*base, "enable", "--now", unit])
    if action == "remove":
        if path.is_file():
            _run([*base, "disable", "--now", unit])
            path.unlink()
            _run([*base, "daemon-reload"])
        return 0
    command = "is-active" if action == "status" else action
    return _run([*base, command, unit], check=action != "status")


def _windows_service(action: str, name: str, launch: ServiceLaunch | None) -> int:
    if launch:
        user = "\\".join(filter(None, (os.environ.get("USERDOMAIN"), getpass.getuser())))
        with TemporaryDirectory() as temp:
            path = Path(temp) / "worker.xml"
            path.write_bytes(scheduled_task(launch, user))
            _run(["schtasks", "/Create", "/TN", name, "/XML", str(path), "/F"])
        return _run(["schtasks", "/Run", "/TN", name])
    if action == "remove":
        _run(["schtasks", "/End", "/TN", name], check=False, quiet=True)
        return _run(["schtasks", "/Delete", "/TN", name, "/F"])
    if action == "status":
        return _run(["schtasks", "/Query", "/TN", name, "/FO", "LIST"], check=False)
    return _run(["schtasks", "/Run" if action == "start" else "/End", "/TN", name])


def manage_service(action: str, config: Path, launch: ServiceLaunch | None = None) -> int:
    manager = {"darwin": _mac_service, "linux": _linux_service, "win32": _windows_service}.get(
        sys.platform
    )
    if manager is None:
        raise ServiceError("当前操作系统不支持工作机后台服务")
    return manager(action, service_name(config), launch)
