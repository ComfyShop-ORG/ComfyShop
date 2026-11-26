"""分块接收并校验原文件。"""

import hashlib
import json
import math
import os
import subprocess
import warnings
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from uuid import uuid4
from xml.parsers import expat

from anyio import to_thread
from PIL import Image, UnidentifiedImageError

from comfyshop_media.errors import MediaError
from comfyshop_media.model_exports import FBX_CONTENT_TYPE, GLB_CONTENT_TYPE, inspect_model_export

_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/avif",
    "image/tiff",
}
_AUDIO_MIME_TYPES = {
    "aac": "audio/aac",
    "flac": "audio/flac",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
}
SVG_CONTENT_TYPE = "image/svg+xml"
TEXT_EXPORT_CONTENT_TYPES = {
    ".txt": "text/plain",
    ".json": "application/json",
    ".svg": SVG_CONTENT_TYPE,
}
_RAW_AUDIO_TYPES = {
    ".pcm": ("audio/x-pcm", 2),
    ".raw": ("audio/x-pcm", 2),
    ".mulaw": ("audio/x-mulaw", 1),
    ".ulaw": ("audio/x-mulaw", 1),
    ".alaw": ("audio/x-alaw", 1),
}
_CONTAINER_CONTENT_TYPES = {
    "mp4": ("audio/mp4", "video/mp4"),
    "matroska": ("audio/x-matroska", "video/x-matroska"),
    "webm": ("audio/webm", "video/webm"),
}
ASSET_UPLOAD_CONTENT_TYPES = frozenset(
    {
        *_IMAGE_CONTENT_TYPES,
        *_AUDIO_MIME_TYPES.values(),
        *(mime for mime, _ in _RAW_AUDIO_TYPES.values()),
        *(mime for pair in _CONTAINER_CONTENT_TYPES.values() for mime in pair),
        GLB_CONTENT_TYPE,
    }
)
_FBX_BINARY_HEADER = b"Kaydara FBX Binary  \x00\x1a\x00"
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs"}


@dataclass
class ReceivedMedia:
    """刚写入磁盘且已验证的文件信息，由调用方决定是否提交数据库记录。"""

    path: Path
    sha256: str
    size: int
    content_type: str
    width: int | None
    height: int | None
    duration_ms: int | None = None


async def receive_media(
    chunks: AsyncIterable[bytes],
    directory: Path,
    limit: int,
    ffprobe: str,
    expected_hash: str | None = None,
    *,
    export_filename: str | None = None,
    source_filename: str | None = None,
) -> ReceivedMedia:
    """将字节流分块写入 `directory`，返回实际路径、摘要、类型和尺寸。

    `limit` 是字节上限，`expected_hash` 提供时须与实算 SHA-256 一致。
    接收失败时尝试删除本次写入的文件。
    """
    await to_thread.run_sync(lambda: directory.mkdir(parents=True, exist_ok=True, mode=0o700))
    path = directory / uuid4().hex
    checksum = hashlib.sha256()
    size = 0
    try:
        with path.open("xb") as output:
            os.chmod(path, 0o600)
            async for chunk in chunks:
                size += len(chunk)
                if size > limit:
                    raise MediaError("too_large", "文件过大")
                checksum.update(chunk)
                await to_thread.run_sync(output.write, chunk)
        digest = checksum.hexdigest()
        if not size or (expected_hash and digest != expected_hash):
            raise MediaError("invalid", "文件校验失败")
        kind, width, height, duration_ms = await to_thread.run_sync(
            inspect_media, path, ffprobe, export_filename, source_filename
        )
        return ReceivedMedia(path, digest, size, kind, width, height, duration_ms)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _is_glb(path: Path) -> bool:
    with path.open("rb") as source:
        header = source.read(20)
        if header[:4] != b"glTF":
            return False
        if len(header) != 20:
            raise MediaError("invalid", "GLB 文件头不完整")
        version, size, metadata_size, chunk_type = unpack("<III4s", header[4:])
        if (
            version != 2
            or size != path.stat().st_size
            or chunk_type != b"JSON"
            or not 4 <= metadata_size <= min(size - 20, 32 * 1024 * 1024)
            or metadata_size % 4
        ):
            raise MediaError("invalid", "GLB 文件头或元数据大小无效")
        try:
            info = json.loads(source.read(metadata_size))
            if info["asset"]["version"] != "2.0":
                raise ValueError()
        except (KeyError, TypeError, ValueError, RecursionError):
            raise MediaError("invalid", "GLB 元数据无效") from None
        if source.tell() < size:
            chunk = source.read(8)
            if len(chunk) != 8:
                raise MediaError("invalid", "GLB 数据块不完整")
            length, kind = unpack("<I4s", chunk)
            if kind != b"BIN\x00" or length % 4 or source.tell() + length != size:
                raise MediaError("invalid", "GLB 数据块无效")
    return True


def _is_fbx(path: Path) -> bool:
    with path.open("rb") as source:
        header = source.read(4096)
    if header.startswith(_FBX_BINARY_HEADER):
        return len(header) > 40 and int.from_bytes(header[23:27], "little") >= 6000
    first_line, _, content = header.partition(b"\n")
    return (
        first_line.startswith(b"; FBX ")
        and b" project file" in first_line
        and b"FBXHeaderExtension:" in content
    )


def _is_heif(path: Path) -> bool:
    """按 ISO BMFF 的文件类型识别 HEIF，避免用文件名误判系统转码后的 JPEG。"""
    with path.open("rb") as source:
        header = source.read(8)
        if len(header) != 8:
            return False
        size, kind = unpack(">I4s", header)
        if kind != b"ftyp" or not 16 <= size <= 4096 or size % 4:
            return False
        payload = source.read(size - 8)
    if len(payload) != size - 8:
        return False
    brands = {payload[:4], *(payload[i : i + 4] for i in range(8, len(payload), 4))}
    return bool(brands & _HEIF_BRANDS) or (
        bool(brands & {b"mif1", b"msf1"}) and not brands & {b"avif", b"avis"}
    )


def _container_types(path: Path, demuxer: str) -> tuple[str | None, str | None]:
    if "mp4" in demuxer or "mov" in demuxer:
        return _CONTAINER_CONTENT_TYPES["mp4"]
    if "webm" in demuxer:
        with path.open("rb") as source:
            if b"\x42\x82\x88matroska" in source.read(4096):
                return _CONTAINER_CONTENT_TYPES["matroska"]
        return _CONTAINER_CONTENT_TYPES["webm"]
    return _AUDIO_MIME_TYPES.get(demuxer), None


def _validate_svg(path: Path) -> None:
    parser = expat.ParserCreate(encoding="UTF-8", namespace_separator=" ")

    def root(name: str, _attributes: dict[str, str]) -> None:
        if name != "http://www.w3.org/2000/svg svg":
            raise MediaError("invalid", "SVG 根元素无效")
        parser.StartElementHandler = None

    def reject_doctype(*_: object) -> None:
        raise MediaError("invalid", "SVG 不能包含文档类型声明")

    parser.StartElementHandler = root
    parser.StartDoctypeDeclHandler = reject_doctype
    try:
        with path.open("rb") as source:
            parser.ParseFile(source)
    except expat.ExpatError:
        raise MediaError("invalid", "SVG 文件需要 UTF-8 编码和有效的 XML") from None


def inspect_media(
    path: Path,
    ffprobe: str,
    export_filename: str | None = None,
    source_filename: str | None = None,
) -> tuple[str, int | None, int | None, int | None]:
    """从文件内容识别 MIME 类型、宽高和可用的媒体时长。"""
    if _is_glb(path):
        return GLB_CONTENT_TYPE, None, None, None
    if _is_fbx(path):
        return FBX_CONTENT_TYPE, None, None, None
    if export_filename:
        if content_type := inspect_model_export(path, export_filename):
            return content_type, None, None, None
        if content_type := TEXT_EXPORT_CONTENT_TYPES.get(Path(export_filename).suffix.lower()):
            if content_type == SVG_CONTENT_TYPE:
                _validate_svg(path)
                return content_type, None, None, None
            try:
                with path.open(encoding="utf-8") as source:
                    while source.read(64 * 1024):
                        pass
            except UnicodeError:
                raise MediaError("invalid", "文本成品需要 UTF-8 编码") from None
            return content_type, None, None, None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                content_type = Image.MIME.get(image.format or "")
                if content_type not in _IMAGE_CONTENT_TYPES:
                    raise MediaError("invalid", "不支持的图像格式")
                width, height = image.size
                image.verify()
                return content_type, width, height, None
    except UnidentifiedImageError:
        pass
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MediaError("invalid", "图像文件无效") from None
    if _is_heif(path):
        raise MediaError(
            "invalid",
            "当前不支持 HEIC 或 HEIF。可在 iPhone「文件」中长按图片，"
            "通过「快速操作 → 转换图像」转为 JPEG 或 PNG 后上传。",
        )
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm,aac,flac,mp3,wav,ogg",
                "-show_entries",
                "stream=codec_type,codec_name,width,height:stream_disposition=attached_pic:"
                "format=format_name,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=20,
            check=True,
        )
        info = json.loads(result.stdout)
        kind = info["format"]["format_name"]
        audio_type, video_type = _container_types(path, kind)
        video = next(
            (
                track
                for track in info["streams"]
                if track.get("codec_type") == "video"
                and not track.get("disposition", {}).get("attached_pic")
            ),
            None,
        )
        raw = info["format"].get("duration", "N/A")
        duration = float(raw) * 1000 if raw != "N/A" else 0
        duration_ms = round(duration) if math.isfinite(duration) and 0 < duration < 2**63 else None
        if video is None and audio_type:
            audio = next(track for track in info["streams"] if track.get("codec_type") == "audio")
            if kind in {"aac", "flac", "mp3"} and audio.get("codec_name") != kind:
                raise ValueError()
            return audio_type, None, None, duration_ms
        if not video_type or video is None:
            raise ValueError()
        width, height = int(video["width"]), int(video["height"])
        if not 0 < width <= 32768 or not 0 < height <= 32768:
            raise ValueError()
        return video_type, width, height, duration_ms
    except FileNotFoundError:
        raise MediaError("unavailable", "服务器需要安装 ffprobe 才能接收音频或视频") from None
    except (subprocess.SubprocessError, ValueError, KeyError, StopIteration):
        raw_type = _RAW_AUDIO_TYPES.get(
            Path(source_filename or export_filename or "").suffix.lower()
        )
        if raw_type:
            content_type, sample_bytes = raw_type
            size = path.stat().st_size
            if size > 0 and size % sample_bytes == 0:
                return content_type, None, None, None
        raise MediaError("invalid", "文件不是受支持的图像、视频、音频或 3D 模型") from None
