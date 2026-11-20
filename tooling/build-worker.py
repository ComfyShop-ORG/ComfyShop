"""把独立工作机源码、锁定的依赖和启动器打包到 Web 下载目录。"""

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
with TemporaryDirectory(dir=output.parent) as temporary:
    archive = Path(temporary) / output.name
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in sorted((worker / "comfyshop_worker").glob("*.py")):
            bundle.writestr(f"{archive_root}/comfyshop_worker/{path.name}", path.read_bytes())
        bundle.writestr(f"{archive_root}/requirements.txt", requirements)
        for name in ("pyproject.toml", "README.md"):
            bundle.writestr(f"{archive_root}/{name}", (worker / name).read_bytes())
        for name in ("start.cmd", "start.command", "start.sh"):
            launcher = (worker / "standalone" / name).read_text(encoding="utf-8")
            if name.endswith(".cmd"):
                launcher = launcher.replace("\n", "\r\n")
            entry = ZipInfo(f"{archive_root}/{name}")
            entry.create_system = 3
            entry.external_attr = (0o100644 if name.endswith(".cmd") else 0o100755) << 16
            bundle.writestr(entry, launcher.encode("utf-8"), compress_type=ZIP_DEFLATED)
    archive.replace(output)
