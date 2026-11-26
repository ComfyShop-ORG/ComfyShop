from pathlib import Path
from zipfile import ZipFile

import pytest

from comfyshop_media.errors import MediaError
from comfyshop_media.model_exports import inspect_model_export


def test_model_zip_requires_a_model_entry(tmp_path: Path) -> None:
    path = tmp_path / "download"
    with ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", "example text")
    with pytest.raises(MediaError, match="ZIP 模型成品格式无效"):
        inspect_model_export(path, "result.zip")

    with ZipFile(path, "a") as archive:
        archive.writestr("model.obj", "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert inspect_model_export(path, "result.zip") == "application/zip"
