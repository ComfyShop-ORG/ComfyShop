"""Recognize model exports for delivery as original files."""

import math
from pathlib import Path
from struct import unpack_from
from zipfile import ZIP_STORED, BadZipFile, ZipFile

from comfyshop_media.errors import MediaError

GLB_CONTENT_TYPE = "model/gltf-binary"
FBX_CONTENT_TYPE = "application/x-fbx"
MTL_CONTENT_TYPE = "model/mtl"
EXPORT_CONTENT_TYPES = {
    ".obj": "model/obj",
    ".mtl": MTL_CONTENT_TYPE,
    ".stl": "model/stl",
    ".usdz": "model/vnd.usdz+zip",
    ".3mf": "model/3mf",
    ".zip": "application/zip",
}
MODEL_DOWNLOAD_CONTENT_TYPES = frozenset((*EXPORT_CONTENT_TYPES.values(), FBX_CONTENT_TYPE))
MODEL_CONTENT_TYPES = MODEL_DOWNLOAD_CONTENT_TYPES | {GLB_CONTENT_TYPE}
MESH_CONTENT_TYPES = MODEL_CONTENT_TYPES - {MTL_CONTENT_TYPE}
MAX_ZIP_DIRECTORY_BYTES = 16 * 1024 * 1024


def _has_obj_vertex(header: bytes) -> bool:
    for line in header.splitlines():
        tokens = line.split()
        if len(tokens) < 4 or tokens[0] != b"v":
            continue
        try:
            if all(math.isfinite(float(coordinate)) for coordinate in tokens[1:4]):
                return True
        except ValueError:
            continue
    return False


def _is_stl(header: bytes, size: int) -> bool:
    if len(header) >= 84:
        count = unpack_from("<I", header, 80)[0]
        if count and 84 + 50 * count == size:
            return True
    return (
        header.lstrip().startswith((b"solid ", b"solid\t", b"solid\r", b"solid\n"))
        and b"facet normal" in header
        and b"vertex" in header
    )


def _is_model_archive(path: Path, suffix: str) -> bool:
    # 只读归档目录。先检查标准结束记录，限制 ZipFile 分配的目录数据。
    with path.open("rb") as source:
        source.seek(-min(path.stat().st_size, 65557), 2)
        tail = source.read()
    end = tail.rfind(b"PK\x05\x06")
    if end < 0 or end + 22 > len(tail):
        return False
    if end >= 20 and tail[end - 20 : end - 16] == b"PK\x06\x07":
        return False
    directory_size = unpack_from("<I", tail, end + 12)[0]
    if not 0 < directory_size <= MAX_ZIP_DIRECTORY_BYTES:
        return False
    try:
        with ZipFile(path) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            names = {entry.filename.lower() for entry in entries}
            if suffix == ".usdz":
                return all(entry.compress_type == ZIP_STORED for entry in entries) and any(
                    name.endswith((".usd", ".usda", ".usdc")) for name in names
                )
            if suffix == ".zip":
                return any(
                    name.endswith(
                        (
                            ".obj",
                            ".glb",
                            ".gltf",
                            ".fbx",
                            ".stl",
                            ".usd",
                            ".usda",
                            ".usdc",
                            ".usdz",
                            ".3mf",
                        )
                    )
                    for name in names
                )
            return "[content_types].xml" in names and any(
                name.startswith("3d/") and name.endswith(".model") for name in names
            )
    except (BadZipFile, UnicodeError, ValueError):
        return False


def inspect_model_export(path: Path, filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    content_type = EXPORT_CONTENT_TYPES.get(suffix)
    if content_type is None:
        return None
    with path.open("rb") as source:
        header = source.read(65536)
    if suffix == ".obj":
        valid = b"\x00" not in header and _has_obj_vertex(header.removeprefix(b"\xef\xbb\xbf"))
    elif suffix == ".mtl":
        valid = b"\x00" not in header and any(
            line.lstrip().startswith((b"newmtl ", b"newmtl\t"))
            for line in header.removeprefix(b"\xef\xbb\xbf").splitlines()
        )
    elif suffix == ".stl":
        valid = _is_stl(header, path.stat().st_size)
    else:
        valid = header.startswith(b"PK\x03\x04") and _is_model_archive(path, suffix)
    if not valid:
        raise MediaError("invalid", f"{suffix.removeprefix('.').upper()} 模型成品格式无效")
    return content_type
