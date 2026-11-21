"""把独立工作机源码、锁定的依赖和启动器打包到 Web 下载目录。"""

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


root = Path(__file__).resolve().parent.parent
worker = root / "integrations/comfyui"
project = tomllib.loads((worker / "pyproject.toml").read_text(encoding="utf-8"))["project"]
archive_root = f"comfyshop-worker-{project['version']}"
output = root / "dist/downloads/comfyshop-worker.zip"

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
    cwd=root,
)
output.parent.mkdir(parents=True, exist_ok=True)
files = {
    f"comfyshop_worker/{path.name}": path.read_bytes()
    for path in (worker / "comfyshop_worker").glob("*.py")
}
files["requirements.txt"] = requirements
for name in ("pyproject.toml", "README.md"):
    files[name] = (worker / name).read_bytes()
launchers = {"start.cmd", "start.command", "start.sh"}
for name in launchers:
    launcher = (worker / "standalone" / name).read_text(encoding="utf-8")
    files[name] = (launcher.replace("\n", "\r\n") if name == "start.cmd" else launcher).encode(
        "utf-8"
    )
identity = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
build = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
files["comfyshop_worker/worker-build.json"] = json.dumps(
    {"version": project["version"], "build": build}, sort_keys=True
).encode("utf-8")

with TemporaryDirectory(dir=output.parent) as temporary:
    archive = Path(temporary) / output.name
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, data in sorted(files.items()):
            entry = ZipInfo(f"{archive_root}/{name}")
            entry.create_system = 3
            entry.external_attr = (
                0o100755 if name in {"start.command", "start.sh"} else 0o100644
            ) << 16
            bundle.writestr(entry, data, compress_type=ZIP_DEFLATED)
    archive.replace(output)
