"""生成和复用缩略图、视频封面和短片。"""

import logging
import subprocess
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from io import BytesIO
from os import fstat
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore, Lock

from PIL import Image, ImageOps

from comfyshop_media.errors import MediaError
from comfyshop_media.settings import MediaSettings

THUMBNAIL_SIZES = (160, 256, 384, 512, 768, 1024, 1280)
MAX_THUMBNAIL_SIZE = THUMBNAIL_SIZES[-1]
MAX_VIDEO_PREVIEW_SIZE = 768
VIDEO_POSTER_SIZE = 960
DEFAULT_IMAGE_SIZE = 512
COMMON_CARD_SIZES = (384, 512)
# 修改输出格式、质量或缩放规则时递增版本，使各存储后端和浏览器得到同一份新结果。
DERIVATIVE_VERSION = "v1"

_cache_locks = tuple(Lock() for _ in range(32))
_decoders = BoundedSemaphore(2)
_preview_locks = tuple(Lock() for _ in range(8))
_preview_encoders = BoundedSemaphore(2)
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaSource:
    storage_name: str
    sha256: str
    content_type: str
    width: int
    height: int


def _thumbnail_name(media: MediaSource, size: int, frame_ms: int) -> str:
    extension = "jpg" if media.content_type.startswith("video/") else "webp"
    return f"{DERIVATIVE_VERSION}-{media.sha256}-{size}-{frame_ms}.{extension}"


def _thumbnail_size(media: MediaSource, requested: int | None) -> int:
    """把请求的长边归到档位。视频不指定尺寸时取封面尺寸。"""
    if requested is None and media.content_type.startswith("video/"):
        return min(max(media.width, media.height), VIDEO_POSTER_SIZE)
    return _size_at_least(
        thumbnail_sizes(media.width, media.height), requested or DEFAULT_IMAGE_SIZE
    )


def thumbnail_key(media: MediaSource, requested: int | None, frame_ms: int) -> str:
    return _thumbnail_name(media, _thumbnail_size(media, requested), frame_ms)


def thumbnail_sizes(width: int, height: int, *, maximum: int = MAX_THUMBNAIL_SIZE) -> list[int]:
    """返回递增长边档位，末档取原始长边与 `maximum` 中较小的值。"""
    limit = min(maximum, max(width, height))
    return [size for size in THUMBNAIL_SIZES if size < limit] + [limit]


def _size_at_least(sizes: list[int], requested: int) -> int:
    return next((size for size in sizes if size >= requested), sizes[-1])


def _cached(config: MediaSettings, target: Path) -> bytes | None:
    try:
        with target.open("rb") as file:
            if config.media_storage.derivative_is_current(fstat(file.fileno())):
                return file.read() or None
    except FileNotFoundError:
        return None
    except OSError:
        _log.warning("无法读取缩略图缓存", exc_info=True)
    return None


def _restore(config: MediaSettings, target: Path) -> bool:
    try:
        return config.media_storage.restore_derivative(target)
    except OSError:
        _log.warning("无法读取对象存储中的派生文件", exc_info=True)
        return False


def _persist(config: MediaSettings, source: Path, target: Path, content_type: str) -> None:
    try:
        config.media_storage.persist_derivative(source, target, content_type)
    except OSError:
        _log.warning("无法保存派生文件到对象存储", exc_info=True)


def _store(config: MediaSettings, target: Path, content: bytes, content_type: str) -> None:
    if len(content) > config.derivative_cache_max_bytes:
        return
    try:
        with config.media_storage.staging_directory() as directory:
            source = Path(directory) / "thumbnail"
            source.write_bytes(content)
            _persist(config, source, target, content_type)
    except OSError:
        _log.warning("无法写入缩略图缓存", exc_info=True)


def _image(source: Path, sizes: list[int]) -> dict[int, bytes]:
    try:
        with Image.open(source) as original:
            if Image.MAX_IMAGE_PIXELS and original.width * original.height > Image.MAX_IMAGE_PIXELS:
                raise MediaError("invalid", "图像尺寸过大")
            prepared: AbstractContextManager[Image.Image] = nullcontext(original)
            if original.mode not in {"RGB", "RGBA"} or "transparency" in original.info:
                alpha = "A" in original.getbands() or "transparency" in original.info
                prepared = original.convert("RGBA" if alpha else "RGB")
            results = {}
            with prepared as image:
                image.load()
                for size in sizes:
                    # 共用一次解码，生成结果也与本次缓存缺少几个尺寸无关。
                    variant = image.copy() if len(sizes) > 1 else nullcontext(image)
                    with variant as scaled:
                        scaled.thumbnail((size, size), Image.Resampling.LANCZOS, reducing_gap=2)
                        ImageOps.exif_transpose(scaled, in_place=True)
                        with BytesIO() as output:
                            scaled.save(
                                output,
                                format="WEBP",
                                quality=82,
                                icc_profile=scaled.info.get("icc_profile"),
                            )
                            results[size] = output.getvalue()
            return results
    except FileNotFoundError:
        raise MediaError("missing", "媒体原文件不存在") from None
    except (OSError, ValueError, Image.DecompressionBombError):
        raise MediaError("unavailable", "暂时无法生成图片缩略图") from None


def _video_input(source: Path, ffmpeg: str, start_ms: int = 0) -> list[str]:
    """读取视频的 ffmpeg 参数。`start_ms` 大于 0 时从这一刻开始解码。"""
    return [
        ffmpeg,
        "-v",
        "error",
        "-nostdin",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        "mov,matroska,webm",
        # 放在输入之前：先跳到最近的关键帧再解码到这一刻，画面准确且不必从头解码。
        *(["-ss", f"{start_ms / 1000:.3f}"] if start_ms else []),
        "-i",
        str(source),
    ]


def _scale(size: int) -> str:
    return f"scale=w='min({size},iw)':h='min({size},ih)':force_original_aspect_ratio=decrease"


def _video(source: Path, sizes: list[int], ffmpeg: str, frame_ms: int) -> dict[int, bytes]:
    """由同一次视频解码输出各档位的 JPEG 封面。"""
    try:
        with TemporaryDirectory(prefix="comfyshop-poster-") as directory:
            sources = [f"[source{index}]" for index in range(len(sizes))]
            split = f"[0:v:0]split={len(sizes)}{''.join(sources)}"
            filters = [
                split,
                *[
                    f"{label}{_scale(size)}[poster{size}]"
                    for label, size in zip(sources, sizes, strict=True)
                ],
            ]
            command = [
                *_video_input(source, ffmpeg, frame_ms),
                "-filter_complex_threads",
                "1",
                "-filter_complex",
                ";".join(filters),
            ]
            paths = {size: Path(directory) / f"{size}.jpg" for size in sizes}
            for size, target in paths.items():
                command.extend(
                    [
                        "-map",
                        f"[poster{size}]",
                        "-frames:v",
                        "1",
                        "-map_metadata",
                        "-1",
                        "-c:v",
                        "mjpeg",
                        "-q:v",
                        "4",
                        "-threads",
                        "1",
                        "-f",
                        "image2",
                        "-update",
                        "1",
                        str(target),
                    ]
                )
            subprocess.run(command, capture_output=True, timeout=20, check=True)
            content = {size: path.read_bytes() for size, path in paths.items()}
            if all(content.values()):
                return content
    except (OSError, subprocess.SubprocessError):
        pass
    raise MediaError("unavailable", "暂时无法生成视频封面")


def _duration_ms(source: Path, ffprobe: str) -> int:
    """视频长度，单位毫秒。读不出来返回 503。"""
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            capture_output=True,
            timeout=20,
            check=True,
        )
        return int(float(result.stdout.decode().strip()) * 1000)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise MediaError("unavailable", "暂时无法读取视频长度") from None


def cover_frame(media: MediaSource, config: MediaSettings, frame_ms: int | None) -> int | None:
    """核对封面画面的时间点并返回要保存的值，用首帧时返回 `None`。

    只有视频可以指定画面，时间须在视频长度之内，否则返回 422。核对通过后随即截出这一帧，
    截好的封面留在缓存里，随后的读取不必再等。
    """
    if not frame_ms:
        return None
    if not media.content_type.startswith("video/"):
        raise MediaError("invalid", "只有视频可以选择封面画面")
    with config.media_storage.local_original(media.storage_name) as source:
        if frame_ms >= _duration_ms(source, config.ffprobe):
            raise MediaError("invalid", "所选时间超出视频长度")
        read_thumbnail(media, config, None, frame_ms, original=source)
    return frame_ms


def read_thumbnail(
    media: MediaSource,
    config: MediaSettings,
    requested: int | None,
    frame_ms: int = 0,
    *,
    original: Path | None = None,
) -> tuple[bytes, str]:
    """按 `requested` 的目标长边返回图像字节及 MIME 类型，首次请求生成并缓存。

    图片使用 WebP，视频封面使用 JPEG，`frame_ms` 指定视频取哪一刻的画面，默认首帧。
    原文件缺失返回 404，图片超出解码尺寸限制或时间超出视频长度返回 422，解码或封面
    生成失败返回 503。
    """
    video = media.content_type.startswith("video/")
    size = _thumbnail_size(media, requested)
    content_type = "image/jpeg" if video else "image/webp"
    target = config.thumbnail_dir / _thumbnail_name(media, size, frame_ms)
    content = _cached(config, target)
    if content is not None:
        return content, content_type
    # 不同尺寸在同一把锁内补齐。同一内容与画面只需读取一次原件。
    with _cache_locks[hash((media.sha256, frame_ms)) % len(_cache_locks)]:
        content = _cached(config, target)
        if content is None and _restore(config, target):
            content = _cached(config, target)
        if content is not None:
            return content, content_type

        sizes = thumbnail_sizes(media.width, media.height)
        common = sorted({_size_at_least(sizes, edge) for edge in COMMON_CARD_SIZES})
        missing = {size: target}
        if size in common:
            for companion in common:
                if companion == size:
                    continue
                path = config.thumbnail_dir / _thumbnail_name(media, companion, frame_ms)
                if _cached(config, path) is None and not _restore(config, path):
                    missing[companion] = path
        local = (
            nullcontext(original)
            if original is not None
            else config.media_storage.local_original(media.storage_name)
        )
        with _decoders, local as source:
            result = (
                _video(source, list(missing), config.ffmpeg, frame_ms)
                if video
                else _image(source, list(missing))
            )
        for edge, path in missing.items():
            _store(config, path, result[edge], content_type)
        return result[size], content_type


def _encode_preview(source: Path, target: Path, size: int, ffmpeg: str) -> None:
    try:
        subprocess.run(
            [
                *_video_input(source, ffmpeg),
                "-y",
                "-abort_on",
                "empty_output",
                "-map",
                "0:V:0",
                "-an",
                "-t",
                "10",
                "-filter_threads",
                "1",
                "-vf",
                f"fps=24:round=up,{_scale(size)},pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-map_metadata",
                "-1",
                "-map_chapters",
                "-1",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "27",
                "-maxrate",
                "960k",
                "-bufsize",
                "960k",
                "-threads",
                "1",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(target),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise MediaError("unavailable", "暂时无法生成视频预览") from None


def video_preview(media: MediaSource, config: MediaSettings, requested: int, output: Path) -> Path:
    """将 MP4 短片写入调用方持有的暂存路径。"""
    if not media.content_type.startswith("video/"):
        raise MediaError("missing", "视频预览不存在")
    sizes = thumbnail_sizes(media.width, media.height, maximum=MAX_VIDEO_PREVIEW_SIZE)
    size = _size_at_least(sizes, requested)
    target = config.video_preview_dir / f"{DERIVATIVE_VERSION}-{media.sha256}-{size}.mp4"
    storage = config.media_storage
    if storage.reuse_derivative(target, output):
        return output
    with _preview_locks[hash(target) % len(_preview_locks)]:
        if storage.reuse_derivative(target, output):
            return output
        if _restore(config, target) and storage.reuse_derivative(target, output):
            return output
        if not _preview_encoders.acquire(blocking=False):
            raise MediaError("unavailable", "视频预览正在生成，请稍后重试")
        try:
            with storage.local_original(media.storage_name) as source:
                _encode_preview(source, output, size, config.ffmpeg)
            _persist(config, output, target, "video/mp4")
        finally:
            _preview_encoders.release()
    return output
