"""把独立工作机源码、锁定的依赖和启动器打包到 Web 下载目录。"""

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / "integrations/comfyui"


def build_package(output: Path, version: str | None) -> None:
    source = (WORKER / "pyproject.toml").read_bytes()
    project = tomllib.loads(source.decode("utf-8"))["project"]
    if version:
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})(?:\.(?:0|[1-9][0-9]{0,5})){2}", version):
            raise ValueError("无效的工作机版本")
        source = source.replace(
            f'version = "{project["version"]}"'.encode(), f'version = "{version}"'.encode(), 1
        )
        assert tomllib.loads(source.decode("utf-8"))["project"]["version"] == version
    else:
        version = project["version"]

    # 只导出工作机依赖。下载包在用户机器上创建环境并校验依赖文件的哈希。
    requirements = subprocess.check_output(
        [
            "uv",
            "export",
            "--locked",
            "--package",
            "comfyshop-worker",
            "--no-dev",
            "--no-emit-workspace",
            "--no-header",
            "--no-annotate",
        ],
        cwd=ROOT,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    files = {
        f"{package.name}/{path.name}": path.read_bytes()
        for package in (
            WORKER / "comfyshop_worker",
            ROOT / "libs/worker-protocol/comfyshop_worker_protocol",
        )
        for path in package.glob("*.py")
    }
    files.update(
        {
            "requirements.txt": requirements,
            "pyproject.toml": source,
            "README.md": (WORKER / "README.md").read_bytes(),
        }
    )
    for name in ("start.cmd", "start.command", "start.sh"):
        launcher = (WORKER / "standalone" / name).read_text(encoding="utf-8")
        files[name] = (launcher.replace("\n", "\r\n") if name == "start.cmd" else launcher).encode(
            "utf-8"
        )
    identity = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    build = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    files["comfyshop_worker/worker-build.json"] = json.dumps(
        {"version": version, "build": build}, sort_keys=True
    ).encode("utf-8")

    with TemporaryDirectory(dir=output.parent) as temporary:
        archive = Path(temporary) / output.name
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for name, data in sorted(files.items()):
                entry = ZipInfo(f"comfyshop-worker-{version}/{name}")
                entry.create_system = 3
                entry.external_attr = (
                    0o100755 if name in {"start.command", "start.sh"} else 0o100644
                ) << 16
                bundle.writestr(entry, data, compress_type=ZIP_DEFLATED)
        archive.replace(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/downloads/comfyshop-worker.zip")
    parser.add_argument("--test-version", help="Version override for isolated update tests")
    args = parser.parse_args()
    if args.test_version and args.output.resolve() == parser.get_default("output").resolve():
        parser.error("--test-version requires a separate --output")
    build_package(args.output, args.test_version)
