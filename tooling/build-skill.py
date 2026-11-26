"""从仓库里的 Skill 源码生成平台下载包和安装入口。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent


def build_skill(output: Path) -> None:
    skill = ROOT / "integrations/skills/comfyshop"
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output) as temporary:
        installer = Path(temporary) / "install-comfyshop-skill.py"
        script = (skill / "scripts/comfyshop.py").read_bytes()
        installer.write_bytes(script)
        archive = Path(temporary) / "comfyshop-skill.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            bundle.writestr("comfyshop/SKILL.md", (skill / "SKILL.md").read_bytes())
            bundle.writestr("comfyshop/scripts/comfyshop.py", script)
            for name in ("references/generation.md", "references/operations.md"):
                bundle.writestr(f"comfyshop/{name}", (skill / name).read_bytes())
        archive.replace(output / archive.name)
        installer.replace(output / installer.name)


if __name__ == "__main__":
    build_skill(ROOT / "dist/downloads")
