"""分块接收并校验原文件。"""

import json
import hashlib
import math
import os
import subprocess
import warnings
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from uuid import uuid4

from anyio import to_thread
from PIL import Image, UnidentifiedImageError

from comfyshop_media.errors import MediaError


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
) -> ReceivedMedia:
    """将字节流分块写入 `directory`，返回实际路径、摘要、类型和尺寸。

    `limit` 是字节上限，`expected_hash` 提供时须与实算 SHA-256 一致。
    接收失败时尝试删除本次写入的文件。
    """
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
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
        kind, width, height, duration_ms = await to_thread.run_sync(inspect_media, path, ffprobe)
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


def inspect_media(path: Path, ffprobe: str) -> tuple[str, int | None, int | None, int | None]:
    """从文件内容识别 MIME 类型、宽高和可用的音频时长。"""
    if _is_glb(path):
        return "model/gltf-binary", None, None, None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                content_type = Image.MIME.get(image.format or "")
                if content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                    raise MediaError("invalid", "不支持的图像格式")
                width, height = image.size
                image.verify()
                return content_type, width, height, None
    except UnidentifiedImageError:
        pass
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MediaError("invalid", "图像文件无效") from None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm,flac",
                "-show_entries",
                "stream=codec_type,codec_name,width,height:format=format_name,duration",
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
        if kind == "flac" and any(
            track.get("codec_type") == "audio" and track.get("codec_name") == "flac"
            for track in info["streams"]
        ):
            raw = info["format"].get("duration", "N/A")
            duration = float(raw) * 1000 if raw != "N/A" else 0
            duration_ms = (
                round(duration) if math.isfinite(duration) and 0 < duration < 2**63 else None
            )
            return "audio/flac", None, None, duration_ms
        stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
        content_type = (
            "video/webm"
            if "webm" in kind
            else "video/mp4"
            if "mp4" in kind or "mov" in kind
            else None
        )
        width, height = int(stream["width"]), int(stream["height"])
        if not content_type or not 0 < width <= 32768 or not 0 < height <= 32768:
            raise ValueError()
        return content_type, width, height, None
    except FileNotFoundError:
        raise MediaError("unavailable", "服务器需要安装 ffprobe 才能接收音频或视频") from None
    except (subprocess.SubprocessError, ValueError, KeyError, StopIteration):
        raise MediaError("invalid", "文件不是有效的图像、视频、FLAC 音频或 GLB 模型") from None
