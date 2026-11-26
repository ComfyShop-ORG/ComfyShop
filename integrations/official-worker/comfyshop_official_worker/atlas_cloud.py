"""Map a frozen workflow to Atlas Cloud requests and retrieve its predictions."""

import asyncio
import base64
import json
import re
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from math import isfinite
from pathlib import Path
from typing import Annotated, BinaryIO, Literal, Self, TypeGuard

import httpx
from comfyshop_worker_protocol.logging import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    JsonValue,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

ATLAS_ROOT = "https://api.atlascloud.ai/api/v1/model/"
ADAPTER = "atlas-cloud"
MAX_INLINE_OUTPUT_BYTES = 1024**3
GENERATION_TIMEOUT_SECONDS = 30 * 60
MODEL_OUTPUT_SUFFIXES = {
    "GLB": ".glb",
    "PRE_REMESHED_GLB": ".glb",
    "FBX": ".fbx",
    "OBJ": ".obj",
    "MTL": ".mtl",
    "STL": ".stl",
    "USDZ": ".usdz",
    "3MF": ".3mf",
    "ZIP": ".zip",
}
SUBMISSION_UNKNOWN = "Atlas Cloud 可能已受理，暂未取得生成编号。请核实后再重新生成。"
LOGGED_PREDICTION_STATUSES = {
    "pending",
    "queued",
    "starting",
    "processing",
    "running",
    "in_progress",
    "completed",
    "succeeded",
    "timeout",
    "failed",
    "cancelled",
    "canceled",
}


class RunError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


MediaKind = Literal["image", "video", "audio", "3d"]
Base64Format = Literal["image", "zip", "mp4", "mp3", "wav", "pcm"]
InlineFormat = Literal[Base64Format, "text"]
ParameterConditions = dict[str, bool | list[str | int]]
INLINE_AUDIO_CONTENT_TYPES = {
    "m4a": ("audio/mp4",),
    "mp3": ("audio/mpeg", "audio/mp3"),
    "ogg": ("audio/ogg",),
    "wav": ("audio/wav", "audio/wave", "audio/x-wav"),
    "pcm": ("audio/pcm", "audio/x-pcm"),
}


class ImageBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_side: int = Field(default=1, gt=0)
    max_side: int | None = Field(default=None, gt=0)
    min_pixels: int | None = Field(default=None, gt=0)
    max_pixels: int | None = Field(default=None, gt=0)
    max_aspect_ratio: float | None = Field(default=None, ge=1)
    max_aspect_ratio_exclusive: float | None = Field(default=None, gt=1)
    aspect_ratio_range: tuple[FiniteFloat, FiniteFloat] | None = None

    @model_validator(mode="after")
    def validate_sides(self) -> Self:
        if self.max_side is not None and self.min_side > self.max_side:
            raise ValueError("图像边长范围无效")
        if (
            self.min_pixels is not None
            and self.max_pixels is not None
            and self.min_pixels > self.max_pixels
        ):
            raise ValueError("图像像素范围无效")
        if self.aspect_ratio_range is not None:
            minimum, maximum = self.aspect_ratio_range
            if not 0 < minimum <= maximum:
                raise ValueError("宽高比范围无效")
        return self

    def contains(self, width: int, height: int) -> bool:
        short, long = sorted((width, height))
        return (
            self.min_side <= short
            and (self.max_side is None or long <= self.max_side)
            and (self.min_pixels is None or width * height >= self.min_pixels)
            and (self.max_pixels is None or width * height <= self.max_pixels)
            and (self.max_aspect_ratio is None or long <= self.max_aspect_ratio * short)
            and (
                self.max_aspect_ratio_exclusive is None
                or long < self.max_aspect_ratio_exclusive * short
            )
            and (
                self.aspect_ratio_range is None
                or self.aspect_ratio_range[0] <= width / height <= self.aspect_ratio_range[1]
            )
        )


def _asset_duration(name: str, asset: dict) -> int | None:
    duration = (asset.get("media") or {}).get("durationMs")
    if type(duration) is int and duration > 0:
        return duration
    if asset.get("contentType", "").startswith("video/"):
        raise RunError(f"无法读取 {name} 的视频时长，请重新上传视频", retryable=True)
    return None


class MediaSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MediaKind
    fields: list[str] = Field(min_length=1, max_length=100)
    content_types: list[str] = Field(default_factory=list, max_length=20)
    max_bytes: int | None = Field(default=None, gt=0)
    min_duration_ms: int | None = Field(default=None, gt=0)
    max_duration_ms: int | None = Field(default=None, gt=0)
    max_total_duration_ms: int | None = Field(default=None, gt=0)
    image_bounds: ImageBounds | None = None
    reject_png_alpha: bool = False

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("素材槽位重复")
        if self.image_bounds is not None and self.kind not in {"image", "video"}:
            raise ValueError("画面尺寸限制需要图片或视频素材槽位")
        if self.reject_png_alpha and self.kind != "image":
            raise ValueError("PNG 透明通道限制需要图片素材槽位")
        if (
            self.min_duration_ms is not None
            and self.max_duration_ms is not None
            and self.min_duration_ms > self.max_duration_ms
        ):
            raise ValueError("素材时长范围无效")
        return self

    def assets(
        self,
        name: str,
        bound: dict[str, dict],
        *,
        min_items: int = 0,
        duration_cap_ms: int | None = None,
    ) -> list[dict]:
        assets = [bound[field] for field in self.fields if field in bound]
        if len(assets) < min_items:
            raise RunError(f"{name} 至少需要 {min_items} 份素材", retryable=True)
        if self.content_types and any(
            asset.get("contentType") not in self.content_types for asset in assets
        ):
            raise RunError(f"{name} 使用 {'、'.join(self.content_types)} 格式", retryable=True)
        if self.max_bytes is not None and any(asset["size"] > self.max_bytes for asset in assets):
            raise RunError(f"{name} 每份素材最多 {self.max_bytes} 字节", retryable=True)
        caps = (cap for cap in (self.max_duration_ms, duration_cap_ms) if cap is not None)
        maximum_duration = min(caps, default=None)
        if (
            self.min_duration_ms is not None
            or maximum_duration is not None
            or self.max_total_duration_ms is not None
        ):
            total_duration = 0
            for asset in assets:
                duration = _asset_duration(name, asset)
                if duration is None:
                    continue
                total_duration += duration
                if self.min_duration_ms is not None and duration < self.min_duration_ms:
                    raise RunError(
                        f"{name} 每段素材至少 {self.min_duration_ms} 毫秒", retryable=True
                    )
                if maximum_duration is not None and duration > maximum_duration:
                    raise RunError(f"{name} 每段素材最长 {maximum_duration} 毫秒", retryable=True)
            if (
                self.max_total_duration_ms is not None
                and total_duration > self.max_total_duration_ms
            ):
                raise RunError(
                    f"{name} 的 {self.kind} 素材合计最长 {self.max_total_duration_ms} 毫秒",
                    retryable=True,
                )
        if self.image_bounds is not None:
            for asset in assets:
                media = asset.get("media") or {}
                width, height = media.get("width"), media.get("height")
                if (
                    type(width) is int
                    and type(height) is int
                    and not self.image_bounds.contains(width, height)
                ):
                    kind = "参考图" if self.kind == "image" else "视频画面"
                    raise RunError(f"{name} 的{kind}尺寸或宽高比超出范围", retryable=True)
        return assets


class MediaFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    content_types: dict[str, str | list[str]] = Field(min_length=1)
    default: str | None = None


class MediaDurationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    maximum_ms: dict[str, Annotated[int, Field(gt=0)]] = Field(min_length=1)

    def cap(self, payload: dict) -> int | None:
        choice = payload.get(self.parameter)
        return self.maximum_ms.get(choice) if isinstance(choice, str) else None


class VideoTrimLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_ends: int = Field(gt=0)
    max_source_seconds: int = Field(gt=0)
    max_clip_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if not self.default_ends <= self.max_clip_seconds <= self.max_source_seconds:
            raise ValueError("视频剪辑默认时长超出范围")
        return self


class VideoClipFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    ends: str
    fps: str | None = None
    trim: VideoTrimLimits | None = None

    def settings(self, values: dict) -> dict[str, float]:
        start = values.get(self.start)
        ends = values.get(self.ends)
        fps = values.get(self.fps) if self.fps is not None else None
        start = 0 if start is None else start
        if ends is None:
            ends = self.trim.default_ends if self.trim is not None else 0
        fps = 1 if fps is None else fps
        if self.trim is not None and (
            type(start) is not int
            or type(ends) is not int
            or not 0 <= start < ends <= self.trim.max_source_seconds
            or ends - start > self.trim.max_clip_seconds
        ):
            raise RunError(
                f"视频起止时间须为整数，剪辑片段最长 {self.trim.max_clip_seconds} 秒",
                retryable=True,
            )
        if (
            any(
                type(value) not in (int, float) or (type(value) is float and not isfinite(value))
                for value in (start, ends, fps)
            )
            or start < 0
            or ends < 0
            or (ends != 0 and ends <= start)
            or not 0 <= fps <= 24
        ):
            raise RunError("请检查视频起止秒数和采样帧率", retryable=True)
        settings: dict[str, float] = {"start": start, "ends": ends}
        if self.fps is not None:
            settings["fps"] = fps
        return settings


class MediaBinding(MediaSlots):
    encoding: Literal["url", "base64"] = "url"
    array: bool = False
    min_items: int = Field(default=0, ge=0, le=100)
    count_parameter: str | None = None
    max_combined: int | None = Field(default=None, ge=2, le=100)
    format: MediaFormat | None = None
    duration_choice: MediaDurationChoice | None = None
    external_sources_field: str | None = None
    ordered_source_fields: list[str] = Field(default_factory=list)
    allow_additional_sources: bool = False
    external_urls_only: bool = False
    external_https_only: bool = False
    allow_raw_base64: bool = False
    allow_asset_references: bool = False
    allow_oss_references: bool = False
    require_png_alpha: bool = False
    alpha_for_background_parameter: str | None = None
    excluded_output_formats: list[str] = Field(default_factory=list)
    video_clip: VideoClipFields | None = None
    pixel_count_ratio: tuple[FiniteFloat, FiniteFloat] | None = None

    @property
    def has_external_sources(self) -> bool:
        return self.external_sources_field is not None or bool(self.ordered_source_fields)

    @property
    def max_sources(self) -> int | None:
        return None if self.allow_additional_sources else len(self.fields)

    @model_validator(mode="after")
    def validate_array(self) -> Self:
        if (
            (not self.array and len(self.fields) != 1)
            or self.min_items > len(self.fields)
            or (self.max_combined is None) != (self.count_parameter is None)
            or (self.encoding == "base64" and (self.kind != "image" or self.max_bytes is None))
            or (
                self.has_external_sources
                and (
                    self.kind not in {"image", "video", "audio"}
                    or (
                        (self.kind in {"image", "audio"} or self.allow_raw_base64)
                        and not self.external_urls_only
                        and not self.content_types
                    )
                )
            )
            or (
                (self.allow_asset_references or self.allow_oss_references)
                and not self.has_external_sources
            )
            or (
                (self.external_urls_only or self.external_https_only)
                and not self.has_external_sources
            )
            or (
                self.allow_raw_base64
                and (
                    self.kind not in {"image", "video", "audio"}
                    or not self.has_external_sources
                    or self.external_urls_only
                )
            )
            or (
                (self.require_png_alpha or self.alpha_for_background_parameter is not None)
                and self.kind != "image"
            )
            or (
                self.reject_png_alpha
                and (self.require_png_alpha or self.alpha_for_background_parameter is not None)
            )
            or (self.video_clip is not None and (self.kind != "video" or not self.array))
            or (self.duration_choice is not None and self.kind not in {"video", "audio"})
            or (
                self.allow_additional_sources
                and (not self.array or self.external_sources_field is None)
            )
        ):
            raise ValueError("素材映射或数量限制无效")
        if self.ordered_source_fields and (
            not self.array
            or self.external_sources_field is not None
            or len(set(self.ordered_source_fields)) != len(self.fields)
            or len(self.ordered_source_fields) != len(self.fields)
            or self.min_items != len(self.fields)
        ):
            raise ValueError("按顺序绑定的素材来源需要与必填数组槽位一一对应")
        if self.pixel_count_ratio is not None:
            low, high = self.pixel_count_ratio
            if self.kind != "image" or len(self.fields) != 2 or not 0 < low <= high:
                raise ValueError("像素总数比限制需要两张图片和有效的比例范围")
        return self

    def alpha_requirement(self, name: str, payload: dict) -> str | None:
        if self.require_png_alpha:
            return f"{name} 需要一张带透明通道的 PNG"
        if (
            self.alpha_for_background_parameter is not None
            and payload.get(self.alpha_for_background_parameter) == "transparent"
        ):
            return "透明背景需要一张带透明通道的 PNG"
        return None

    @property
    def source_unit(self) -> str:
        return {"image": "张参考图", "video": "段参考视频", "audio": "段参考音频"}.get(
            self.kind, "份素材"
        )

    def external_sources(
        self, name: str, value: object, *, alpha_requirement: str | None, limit: int | None = None
    ) -> list[str]:
        if not isinstance(value, str):
            return []
        sources = [source for line in value.splitlines() if (source := line.strip())]
        maximum = self.max_sources if limit is None else limit
        if maximum is not None and len(sources) > maximum:
            raise RunError(f"{name} 最多 {maximum} {self.source_unit}", retryable=True)
        protocol = "HTTPS" if self.external_https_only else "HTTP(S)"
        for source in sources:
            if _web_url(source, schemes=("http", "https")):
                if self.external_https_only and not _https_url(source):
                    raise RunError(f"{name} 需要可公开访问的 HTTPS 地址", retryable=True)
                continue
            if self.allow_asset_references and re.fullmatch(
                r"asset://[a-zA-Z0-9][a-zA-Z0-9._-]*", source
            ):
                continue
            if (
                self.allow_oss_references
                and _web_url(source, schemes=("oss",))
                and httpx.URL(source).path not in ("", "/")
            ):
                continue
            if self.kind == "video" and not self.allow_raw_base64:
                raise RunError(f"{name} 需要可公开访问的 {protocol} 视频地址", retryable=True)
            media = {"audio": "音频", "video": "视频"}.get(self.kind, "图片")
            if self.external_urls_only:
                raise RunError(f"{name} 需要可公开访问的 {protocol} {media}地址", retryable=True)
            header, separator, encoded = source.partition(",")
            raw_base64 = self.allow_raw_base64 and not separator and not header.startswith("data:")
            content_type = ""
            if raw_base64:
                encoded = source
            else:
                content_type = header.removeprefix("data:").removesuffix(";base64").lower()
                if (
                    not separator
                    or not header.startswith("data:")
                    or not header.endswith(";base64")
                    or content_type not in self.content_types
                ):
                    raise RunError(
                        f"{name} 需要{media}地址或格式受支持的 Base64 素材", retryable=True
                    )
            try:
                content = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise RunError(f"{name} 的 Base64 素材无效", retryable=True) from None
            if not content:
                raise RunError(f"{name} 的 Base64 素材为空", retryable=True)
            if self.max_bytes is not None and len(content) > self.max_bytes:
                raise RunError(f"{name} 每份素材最多 {self.max_bytes} 字节", retryable=True)
            if self.kind == "video":
                detected = _inline_video_type(content)
                if detected not in self.content_types or (
                    content_type and content_type != detected
                ):
                    raise RunError(f"{name} 的 Base64 视频格式不受支持", retryable=True)
            elif self.kind == "audio":
                audio_format = _inline_audio_type(content)
                detected = INLINE_AUDIO_CONTENT_TYPES.get(audio_format or "", ())
                if not (
                    content_type in detected
                    or (raw_base64 and set(detected).intersection(self.content_types))
                ):
                    raise RunError(f"{name} 的 Base64 音频格式不受支持", retryable=True)
            elif raw_base64:
                info = _inline_image_type(content)
                if info is None or info[0] not in self.content_types:
                    raise RunError(f"{name} 的 Base64 图片格式不受支持", retryable=True)
                content_type = info[0]
            if alpha_requirement and (
                content_type != "image/png" or not png_has_alpha(BytesIO(content))
            ):
                raise RunError(alpha_requirement, retryable=True)
            if (
                self.reject_png_alpha
                and content_type == "image/png"
                and png_has_alpha(BytesIO(content))
            ):
                raise RunError(f"{name} 需要不带透明通道的 PNG", retryable=True)
        return sources

    def validate_pixel_count_ratio(self, name: str, assets: list[dict]) -> None:
        if self.pixel_count_ratio is None or len(assets) != 2:
            return
        counts = []
        for asset in assets:
            media = asset.get("media") or {}
            width, height = media.get("width"), media.get("height")
            if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
                return
            counts.append(width * height)
        low, high = self.pixel_count_ratio
        if not low <= counts[0] / counts[1] <= high:
            raise RunError(f"{name} 首尾帧的像素总数比须为 {low:g} 至 {high:g}", retryable=True)


class MediaObjectGroup(MediaSlots):
    external_sources_field: str | None = None


class MediaObjectArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[MediaObjectGroup] = Field(min_length=1, max_length=4)
    requires_any_kind: list[MediaKind] = Field(default_factory=list, max_length=4)
    max_items: int = Field(ge=1, le=100)
    external_https_only: bool = False

    @model_validator(mode="after")
    def validate_groups(self) -> Self:
        kinds = {group.kind for group in self.groups}
        slots = [slot for group in self.groups for slot in group.fields]
        if (
            len(kinds) != len(self.groups)
            or len(set(slots)) != len(slots)
            or set(self.requires_any_kind) - kinds
        ):
            raise ValueError("素材对象数组的分组或类型无效")
        return self

    def external_sources(self, name: str, values: dict) -> list[dict[str, str]]:
        sources = []
        schemes = ("https",) if self.external_https_only else ("http", "https")
        protocol = "HTTPS" if self.external_https_only else "HTTP(S)"
        for group in self.groups:
            value = values.get(group.external_sources_field)
            if not isinstance(value, str):
                continue
            for line in value.splitlines():
                if url := line.strip():
                    if not _web_url(url, schemes=schemes):
                        raise RunError(f"{name} 需要公开的 {protocol} 素材地址", retryable=True)
                    sources.append({"url": url, "type": group.kind})
        return sources

    def assets(
        self, name: str, bound: dict[str, dict], external: list[dict[str, str]]
    ) -> list[dict]:
        groups = {group.kind: group.assets(name, bound) for group in self.groups}
        counts = Counter(source["type"] for source in external)
        for group in self.groups:
            count = len(groups[group.kind]) + counts[group.kind]
            if count > len(group.fields):
                raise RunError(
                    f"{name} 的 {group.kind} 素材最多 {len(group.fields)} 份",
                    retryable=True,
                )
            counts[group.kind] = count
        if self.requires_any_kind and not any(counts[kind] for kind in self.requires_any_kind):
            raise RunError(
                f"{name} 至少需要一种素材（{'、'.join(self.requires_any_kind)}）",
                retryable=True,
            )
        assets = [asset for group in groups.values() for asset in group]
        if len(assets) + len(external) > self.max_items:
            raise RunError(f"{name} 最多接收 {self.max_items} 份素材", retryable=True)
        return assets


@dataclass(frozen=True)
class ReferenceSource:
    key: str
    value: str | dict
    inline: bool = False
    properties: dict[str, int | str] = dataclass_field(default_factory=dict)


class ReferenceAsset(MediaSlots):
    url_key: str
    data_key: str
    inline_field: str

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if len(self.fields) != 1 or self.data_key == self.url_key or self.max_bytes is None:
            raise ValueError("参考素材槽位需要单份有大小限制的文件以及不同的上传字段")
        return self


class ReferenceSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, str] = Field(default_factory=dict)
    asset: ReferenceAsset


class ReferenceArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[ReferenceSlot] = Field(min_length=1, max_length=100)
    max_items: int = Field(ge=1, le=100)
    exclusive_kinds: list[MediaKind] = Field(default_factory=list)

    def sources(self, name: str, values: dict, bound: dict[str, dict]) -> list[ReferenceSource]:
        result = []
        exclusive = False
        for slot in self.slots:
            selected = [
                ReferenceSource(key, source.strip())
                for field, key in slot.values.items()
                if isinstance(source := values.get(field), str) and source.strip()
            ]
            assets = slot.asset.assets(name, bound)
            if len(assets) + len(selected) > 1:
                raise RunError(f"{name} 每个槽位只能选择一种来源", retryable=True)
            if assets:
                inline = values.get(slot.asset.inline_field) is True
                key = slot.asset.data_key if inline else slot.asset.url_key
                selected.append(ReferenceSource(key, assets[0], inline))
                exclusive |= slot.asset.kind in self.exclusive_kinds
            result.extend(selected)
        if len(result) > 1 and exclusive:
            raise RunError(f"{name} 的图片参考须单独使用", retryable=True)
        if len(result) > self.max_items:
            raise RunError(f"{name} 最多 {self.max_items} 项", retryable=True)
        return result


class VideoKeyframeSlot(MediaSlots):
    kind: MediaKind = "image"
    fields: list[str] = Field(min_length=1, max_length=1)
    url_field: str
    index_field: str


class VideoKeyframes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[VideoKeyframeSlot] = Field(min_length=1, max_length=100)
    duration_parameter: str
    frames_per_second: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        if any(slot.kind != "image" for slot in self.slots):
            raise ValueError("关键帧须使用图片素材")
        fields = [
            field
            for slot in self.slots
            for field in (*slot.fields, slot.url_field, slot.index_field)
        ]
        if len(set(fields)) != len(fields):
            raise ValueError("关键帧的图片、地址和帧号字段必须唯一")
        return self

    def sources(
        self, name: str, values: dict, bound: dict[str, dict], payload: dict
    ) -> list[ReferenceSource]:
        duration = payload.get(self.duration_parameter)
        if type(duration) is not int or duration <= 0:
            raise RunError(f"{name} 需要设置整数视频时长", retryable=True)
        maximum = duration * self.frames_per_second
        result = []
        indices = set()
        for slot in self.slots:
            value = values.get(slot.url_field)
            url = value.strip() if isinstance(value, str) else ""
            images = slot.assets(name, bound)
            if not url and not images:
                continue
            if url and images:
                raise RunError(f"{name} 每个关键帧只能选择一种图片来源", retryable=True)
            if url and not _web_url(url, schemes=("http", "https")):
                raise RunError(f"{name} 需要公开的 HTTP(S) 图片地址", retryable=True)
            index = values.get(slot.index_field)
            if type(index) is not int or not 0 <= index <= maximum:
                raise RunError(f"{name} 的帧号须为 0 至 {maximum} 的整数", retryable=True)
            if index in indices:
                raise RunError(f"{name} 的帧号必须唯一", retryable=True)
            indices.add(index)
            result.append(
                ReferenceSource("image_url", url or images[0], properties={"frame_index": index})
            )
        if not result:
            raise RunError(f"{name} 至少需要一张关键帧图片", retryable=True)
        return result


class ImageReferenceSlot(MediaBinding):
    reference_type_field: str
    reference_name_field: str


class ImageReferenceObjects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[ImageReferenceSlot] = Field(min_length=1, max_length=100)
    reference_types: list[str] = Field(min_length=1)
    name_max_bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        if any(
            slot.kind != "image" or slot.array or slot.external_sources_field is None
            for slot in self.slots
        ):
            raise ValueError("图片引用槽位需要一个图片字段和一个来源字段")
        names = [
            field
            for slot in self.slots
            for field in (
                *slot.fields,
                slot.external_sources_field,
                slot.reference_type_field,
                slot.reference_name_field,
            )
        ]
        if len(set(names)) != len(names):
            raise ValueError("图片引用字段不可重复")
        return self

    def sources(self, name: str, values: dict, bound: dict[str, dict]) -> list[ReferenceSource]:
        result = []
        for index, slot in enumerate(self.slots, start=1):
            urls = slot.external_sources(
                name, values.get(slot.external_sources_field), alpha_requirement=None
            )
            images = slot.assets(name, bound)
            if urls and images:
                raise RunError(f"{name} 第 {index} 项只能选择一种图片来源", retryable=True)
            properties: dict[str, int | str] = {}
            reference_type = values.get(slot.reference_type_field)
            if reference_type not in (None, ""):
                if reference_type not in self.reference_types:
                    raise RunError(f"{name} 第 {index} 项的引用类型无效", retryable=True)
                properties["type"] = reference_type
            reference_name = values.get(slot.reference_name_field)
            if isinstance(reference_name, str) and (reference_name := reference_name.strip()):
                if len(reference_name.encode("utf-8")) > self.name_max_bytes:
                    raise RunError(
                        f"{name} 第 {index} 项的引用名最多 {self.name_max_bytes} 字节",
                        retryable=True,
                    )
                properties["ref_name"] = reference_name
            if urls or images:
                result.append(
                    ReferenceSource("image", urls[0] if urls else images[0], properties=properties)
                )
            elif properties:
                raise RunError(f"{name} 第 {index} 项缺少参考图", retryable=True)
        if not result:
            raise RunError(f"{name} 至少需要一张参考图", retryable=True)
        return result


class ImageSizeLimits(ImageBounds):
    parameter: str = "size"
    min_side: int = Field(gt=0)
    allow_auto: bool = True
    auto_requires: str | None = None
    preset_sizes: list[str] = Field(default_factory=list)
    separator: Literal["*", "x"] = "*"
    side_multiple: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        if (
            (self.max_side is None and self.max_pixels is None)
            or (self.min_pixels is None) != (self.max_pixels is None)
            or (self.auto_requires is not None and not self.allow_auto)
        ):
            raise ValueError("图片尺寸范围无效")
        return self

    def validate_size(self, payload: dict) -> None:
        size = payload.get(self.parameter, "auto" if self.allow_auto else None)
        if size is None:
            return
        if size in self.preset_sizes:
            return
        if self.allow_auto and size == "auto":
            if self.auto_requires is not None and payload.get(self.auto_requires) is False:
                raise RunError("使用自动尺寸时请开启提示词扩写", retryable=True)
            return
        if (
            not isinstance(size, str)
            or len(size) > 2 * len(str(self.max_side or self.max_pixels)) + 1
            or (match := re.fullmatch(rf"([0-9]+){re.escape(self.separator)}([0-9]+)", size))
            is None
        ):
            size_format = f"宽{self.separator}高"
            supported = f"auto 或{size_format}" if self.allow_auto else size_format
            raise RunError(f"请输入 {supported} 格式的图片尺寸", retryable=True)
        width, height = map(int, match.groups())
        if width % self.side_multiple or height % self.side_multiple:
            raise RunError(f"图片宽高须为 {self.side_multiple} 的倍数", retryable=True)
        if not self.contains(width, height):
            limits = []
            if self.max_side is not None:
                limits.append(f"每边 {self.min_side}–{self.max_side} 像素")
            if self.min_pixels is not None and self.max_pixels is not None:
                limits.append(f"面积 {self.min_pixels}–{self.max_pixels} 像素")
            if self.max_aspect_ratio is not None:
                limits.append(f"宽高比 1:{self.max_aspect_ratio:g} 至 {self.max_aspect_ratio:g}:1")
            raise RunError(f"图片尺寸超出范围，{'，'.join(limits)}", retryable=True)


class SelectedOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    field: str


class ChoiceArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[SelectedOption] = Field(min_length=1, max_length=100)
    min_items: int = Field(default=1, ge=0, le=100)
    encoding: Literal["array", "comma_separated"] = "array"

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        if (
            len({option.value for option in self.options}) != len(self.options)
            or len({option.field for option in self.options}) != len(self.options)
            or self.min_items > len(self.options)
            or (
                self.encoding == "comma_separated"
                and any("," in option.value for option in self.options)
            )
        ):
            raise ValueError("数组选项的字段或数量无效")
        return self


class ChoiceSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[str] = Field(min_length=1, max_length=100)
    values: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_choices(self) -> Self:
        if (
            len(set(self.fields)) != len(self.fields)
            or len(set(self.values)) != len(self.values)
            or "" in self.values
        ):
            raise ValueError("数组选项的字段与值必须唯一，选项须为非空文本")
        return self

    def items(self, name: str, inputs: dict) -> list[str]:
        selected = [
            value for field in self.fields if (value := inputs.get(field)) not in (None, "")
        ]
        if any(value not in self.values for value in selected):
            raise RunError(f"{name} 含有不支持的选项", retryable=True)
        return selected


class TextArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    min_items: int = Field(default=0, ge=0)
    max_items: int = Field(gt=0)
    max_item_length: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.min_items > self.max_items:
            raise ValueError("文本数组的最少项数不能超过最多项数")
        return self

    def items(self, name: str, value: object) -> list[str]:
        if value is not None and not isinstance(value, str):
            raise RunError(f"{name} 需要按行输入文本", retryable=True)
        items = [line for raw in (value or "").splitlines() if (line := raw.strip())]
        if len(items) < self.min_items:
            raise RunError(f"{name} 至少需要 {self.min_items} 项", retryable=True)
        limit = self.max_item_length
        if len(items) > self.max_items or (
            limit is not None and any(len(item) > limit for item in items)
        ):
            length_hint = f"，每项最多 {limit} 个字符" if limit is not None else ""
            raise RunError(f"{name} 最多 {self.max_items} 项{length_hint}", retryable=True)
        return items


class CompositionChunk(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    text: str
    duration_ms: int = Field(ge=3000, le=120000)
    positive_styles: list[str] = Field(min_length=1)
    negative_styles: list[str] = Field(default_factory=list)
    context_adherence: Literal["low", "medium", "high"] = "high"

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        lines = value.splitlines()
        if len(lines) > 30 or any(len(line) > 200 for line in lines):
            raise ValueError("每段最多 30 行，每行最多 200 个字符")
        return value


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    chunks: list[CompositionChunk] = Field(min_length=1, max_length=30)


def _apply_composition_plan(payload: dict, value: object) -> None:
    prompt = payload.get("prompt")
    has_prompt = isinstance(prompt, str) and bool(prompt.strip())
    if value is None or (isinstance(value, str) and not value.strip()):
        if not has_prompt:
            raise RunError("请填写音乐描述或分段方案", retryable=True)
        return
    if has_prompt or payload.get("force_instrumental") is True:
        raise RunError("使用分段方案时，请清空音乐描述并关闭纯音乐开关", retryable=True)
    try:
        if not isinstance(value, str):
            raise ValueError()
        plan = json.loads(value)
        validated = CompositionPlan.model_validate(plan)
        json.dumps(plan, allow_nan=False)
    except (ValueError, RecursionError):
        raise RunError("分段方案的 JSON、段落时长或风格字段无效", retryable=True) from None
    duration_ms = sum(chunk.duration_ms for chunk in validated.chunks)
    if duration_ms > 600000:
        raise RunError("分段方案总时长最多 600 秒", retryable=True)
    seconds = (duration_ms + 999) // 1000
    if payload.get("duration") != seconds:
        raise RunError(f"分段方案要求将时长设为 {seconds} 秒", retryable=True)
    payload.pop("prompt", None)
    payload.pop("force_instrumental", None)
    payload["composition_plan"] = plan


class DialogueTurn(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    text: str
    voice: str = ""


class DialogueBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    custom_voice_field: str
    default_voice: str

    def apply(self, payload: dict, values: dict) -> None:
        voice = values.get(self.custom_voice_field)
        if isinstance(voice, str) and (voice := voice.strip()):
            payload["voice"] = voice
        value = values.get(self.field)
        try:
            raw = json.loads(value) if isinstance(value, str) and value.strip() else []
            if not isinstance(raw, list):
                raise ValueError()
            turns = [DialogueTurn.model_validate(item) for item in raw]
            json.dumps(raw, allow_nan=False)
        except (ValueError, RecursionError):
            raise RunError("对话需要由台词与可选音色组成的 JSON 数组", retryable=True) from None
        if not turns:
            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                raise RunError("请填写朗读文本或对话", retryable=True)
            return
        fallback = payload.get("voice") or self.default_voice
        if len({turn.voice or fallback for turn in turns}) > 10:
            raise RunError("对话最多使用 10 种音色", retryable=True)
        if sum(len(turn.text) for turn in turns) > 10000:
            raise RunError("对话文本合计最多 10000 个字符", retryable=True)
        if not any(turn.text.strip() for turn in turns):
            raise RunError("请填写对话台词", retryable=True)
        payload.pop("text", None)
        payload["inputs"] = raw


class ParameterCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    equals: str | bool | Annotated[list[str], Field(min_length=1)]


class ChoiceConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    values: dict[str, str | bool | Annotated[list[str], Field(min_length=1)]] = Field(min_length=1)
    default_value: str | None = None


class ChoiceBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    ranges: dict[str, tuple[FiniteFloat, FiniteFloat]] = Field(min_length=1)
    exceptions: list[FiniteFloat] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if any(minimum > maximum for minimum, maximum in self.ranges.values()):
            raise ValueError("选项对应的数值范围无效")
        return self

    def validate_value(self, name: str, payload: dict) -> None:
        value = payload.get(name)
        selection = payload.get(self.parameter)
        bounds = self.ranges.get(str(selection)) if type(selection) in (str, int) else None
        if value is None or bounds is None:
            return
        minimum, maximum = bounds
        if type(value) not in (int, float) or (
            value not in self.exceptions and not minimum <= value <= maximum
        ):
            if minimum == maximum:
                raise RunError(f"{name} 必须为 {minimum:g}", retryable=True)
            raise RunError(f"{name} 必须在 {minimum:g} 至 {maximum:g} 之间", retryable=True)


class MediaBitmask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    media: list[str] = Field(min_length=1)
    width: int = Field(ge=2)

    def validate_request(self, payload: dict, assets: dict[str, list[dict]]) -> None:
        mask = payload.get(self.parameter)
        if mask is None:
            return
        count = sum(len(assets.get(name, [])) for name in self.media)
        if (
            not isinstance(mask, str)
            or len(mask) != self.width
            or set(mask) - {"0", "1"}
            or (count > 1 and mask.count("1") != count)
        ):
            raise RunError(
                f"{self.parameter} 需要 {self.width} 位 0 或 1，多图时 1 的数量须等于图片数量",
                retryable=True,
            )


class MediaParameterMaximum(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum: FiniteFloat
    min_items: int = Field(ge=2, le=100)


class PaletteColor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    ratio: str = Field(pattern=r"^[0-9]+\.[0-9]{2}%$")


def _parse_color_palette(value: str) -> list[dict[str, str]]:
    try:
        raw = json.loads(value)
        if not isinstance(raw, list) or not 3 <= len(raw) <= 10:
            raise ValueError()
        colors = [PaletteColor.model_validate(item) for item in raw]
    except (ValueError, RecursionError):
        raise RunError(
            "调色板需要 3 至 10 个颜色，每项填写六位 HEX 色值和保留两位小数的百分比",
            retryable=True,
        ) from None
    if sum(Decimal(color.ratio[:-1]) for color in colors) != 100:
        raise RunError("调色板百分比合计须为 100.00%", retryable=True)
    return [{"hex": color.hex, "ratio": color.ratio} for color in colors]


class LoRAWeight(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    path: str = Field(pattern=r"\S")
    scale: FiniteFloat = 1


class LoRAArrayLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_items: int = Field(gt=0)
    scale_range: tuple[FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def validate_scale_range(self) -> Self:
        minimum, maximum = self.scale_range
        if minimum > maximum:
            raise ValueError("LoRA 权重范围无效")
        return self


def _parse_lora_list(
    name: str, value: object, shape: Literal["weights", "array"] | LoRAArrayLimits
) -> list:
    try:
        if not isinstance(value, str):
            raise ValueError()
        items = json.loads(value)
        if not isinstance(items, list):
            raise ValueError()
        weights = [LoRAWeight.model_validate(item) for item in items] if shape != "array" else []
        json.dumps(items, allow_nan=False)
    except (ValueError, RecursionError):
        detail = "，每项需要 path，scale 可填有限数值" if shape != "array" else ""
        raise RunError(f"{name} 需要 JSON 数组{detail}", retryable=True) from None
    if isinstance(shape, LoRAArrayLimits):
        if len(weights) > shape.max_items:
            raise RunError(f"{name} 最多 {shape.max_items} 项", retryable=True)
        minimum, maximum = shape.scale_range
        if any(not minimum <= weight.scale <= maximum for weight in weights):
            raise RunError(
                f"{name} 的 scale 需要在 {minimum:g} 至 {maximum:g} 之间", retryable=True
            )
    return items


class KlingShot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt: str = Field(max_length=512)
    duration: int = Field(ge=1)
    index: int | None = None

    @field_validator("duration", mode="before")
    @classmethod
    def parse_seconds(cls, value: object) -> object:
        if isinstance(value, str) and re.fullmatch(r"[1-9]|1[0-5]", value):
            return int(value)
        return value


class KlingElement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    element_id: int | None = Field(default=None, gt=0, le=2**63 - 1)
    element_name: str | None = None
    element_description: str | None = None
    element_voice_id: str | None = None
    reference_type: Literal["image_refer", "video_refer"] = "image_refer"
    frontal_image: str | None = None
    refer_images: list[str] = Field(default_factory=list, max_length=4)
    refer_videos: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        urls = [*self.refer_images, *self.refer_videos]
        if self.frontal_image is not None:
            urls.append(self.frontal_image)
        if any(not _web_url(url, schemes=("https", "http")) for url in urls):
            raise ValueError("主体素材需要公开的 HTTP(S) 地址")
        if self.element_id is not None:
            if self.element_name is not None:
                raise ValueError("已有主体编号和新建主体名称只能提供一个")
        elif not self.element_name or not self.element_name.strip():
            raise ValueError("新建主体需要名称")
        elif self.reference_type == "video_refer":
            if not self.refer_videos:
                raise ValueError("视频主体需要参考视频")
        elif not self.frontal_image:
            raise ValueError("图片主体需要正面图")
        return self


KLING_SHOTS = TypeAdapter(Annotated[list[KlingShot], Field(max_length=6)])
KLING_ELEMENTS = TypeAdapter(list[KlingElement])


def _parse_kling_list[T](name: str, value: object, adapter: TypeAdapter[list[T]]) -> list[T]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    try:
        if not isinstance(value, str):
            raise ValueError()
        return adapter.validate_json(value)
    except ValueError as error:
        detail = (
            error.errors(include_url=False, include_input=False)[0]["msg"]
            if isinstance(error, ValidationError)
            else "需要 JSON 数组"
        )
        raise RunError(f"{name} 无效，{detail}", retryable=True) from None


def _apply_kling_storyboard(payload: dict, value: object, *, indexed: bool) -> None:
    shots = (
        _parse_kling_list("multi_prompt", value, KLING_SHOTS)
        if payload.get("multi_shot") is True
        else []
    )
    if shots:
        if sum(shot.duration for shot in shots) != payload.get("duration", 5):
            raise RunError("分镜时长之和必须等于视频时长", retryable=True)
        payload.pop("prompt", None)
        if indexed:
            payload["multi_prompt"] = [
                {"index": index, "prompt": shot.prompt, "duration": str(shot.duration)}
                for index, shot in enumerate(shots, start=1)
            ]
        else:
            payload["multi_prompt"] = [shot.model_dump(exclude_none=True) for shot in shots]
    elif not isinstance(prompt := payload.get("prompt"), str) or not prompt.strip():
        raise RunError("请填写提示词或启用多镜头并提供分镜方案", retryable=True)


class KlingElementArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    max_items: int = Field(gt=0)
    max_video_subjects: int | None = Field(default=None, ge=0)
    max_image_subjects_with_video: int | None = Field(default=None, ge=0)
    require_reference_type: bool = False
    max_images_per_subject: int = Field(default=4, ge=1, le=4)
    max_videos_per_subject: int = Field(default=4, ge=1, le=4)
    max_name_length: int | None = Field(default=None, gt=0)
    max_description_length: int | None = Field(default=None, gt=0)
    allow_frontal_only: bool = False
    allow_bound_voice: bool = False

    def validate_element(self, element: KlingElement) -> None:
        inline_image = element.element_id is None and element.reference_type == "image_refer"
        if inline_image and not self.allow_frontal_only and not element.refer_images:
            raise RunError("图片主体需要提供参考图", retryable=True)
        if element.element_voice_id is not None and (
            not self.allow_bound_voice or not inline_image
        ):
            raise RunError("只有支持音色绑定的新建图片主体可填写 element_voice_id", retryable=True)
        if (
            self.max_name_length is not None
            and len(element.element_name or "") > self.max_name_length
        ):
            raise RunError(f"主体名称最多 {self.max_name_length} 个字符", retryable=True)
        if (
            self.max_description_length is not None
            and len(element.element_description or "") > self.max_description_length
        ):
            raise RunError(f"主体描述最多 {self.max_description_length} 个字符", retryable=True)

    def items(self, value: object) -> list[dict]:
        elements = _parse_kling_list("elements", value, KLING_ELEMENTS)
        if len(elements) > self.max_items:
            raise RunError(f"主体引用最多 {self.max_items} 项", retryable=True)
        if self.require_reference_type and any(
            item.element_id is None and "reference_type" not in item.model_fields_set
            for item in elements
        ):
            raise RunError("新建主体需要填写 reference_type", retryable=True)
        if any(len(item.refer_images) > self.max_images_per_subject for item in elements):
            raise RunError(f"每个主体最多 {self.max_images_per_subject} 张参考图", retryable=True)
        if any(len(item.refer_videos) > self.max_videos_per_subject for item in elements):
            raise RunError(f"每个主体最多 {self.max_videos_per_subject} 条参考视频", retryable=True)
        for element in elements:
            self.validate_element(element)
        items = [item.model_dump(exclude_none=True, exclude_unset=True) for item in elements]
        counts = _kling_element_types(items)
        videos = counts["video_refer"]
        if self.max_video_subjects is not None and videos > self.max_video_subjects:
            raise RunError(f"视频主体最多 {self.max_video_subjects} 项", retryable=True)
        images_limit = self.max_image_subjects_with_video
        if videos and images_limit is not None and counts["image_refer"] > images_limit:
            raise RunError(f"使用视频主体时最多提供 {images_limit} 项图片主体", retryable=True)
        return items


def _kling_element_types(elements: list[dict]) -> Counter[str]:
    return Counter(
        item.get("reference_type", "image_refer")
        for item in elements
        if "element_id" not in item or "reference_type" in item
    )


class KlingReferenceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_images: int = Field(gt=0)
    max_images_with_video: int = Field(gt=0)

    def apply(self, payload: dict, counts: dict[str, int]) -> None:
        types = _kling_element_types(payload.get("elements", []))
        images = counts.get("images", 0) + types["image_refer"]
        videos = types["video_refer"]
        has_video = bool(counts.get("video"))
        if has_video:
            if "multi_prompt" in payload:
                raise RunError("提供参考视频时，多镜头仅支持自动分镜", retryable=True)
            if videos > 1 or (videos and images):
                raise RunError("有参考视频时，单个视频主体需单独使用", retryable=True)
            payload.pop("sound", None)
        limit = self.max_images_with_video if has_video or videos else self.max_images
        if images > limit:
            raise RunError(f"参考图和图片主体合计最多 {limit} 项", retryable=True)


class ImageAspectRatioMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: tuple[str, str]
    ratio_range: tuple[FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        first, last = self.parameters
        minimum, maximum = self.ratio_range
        if first == last or not 0 < minimum <= maximum:
            raise ValueError("图片配对的宽高比范围无效")
        return self

    def validate_assets(self, assets: dict[str, list[dict]]) -> None:
        sizes = []
        for name in self.parameters:
            if not (selected := assets.get(name)):
                return
            media = selected[0].get("media") or {}
            width, height = media.get("width"), media.get("height")
            if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
                return
            sizes.append((width, height))
        (first_width, first_height), (last_width, last_height) = sizes
        ratio = (first_width * last_height) / (first_height * last_width)
        minimum, maximum = self.ratio_range
        if not minimum <= ratio <= maximum:
            raise RunError(f"首尾帧的宽高比之比须为 {minimum:g} 至 {maximum:g}", retryable=True)


@dataclass(frozen=True)
class ImageSubject:
    id: str
    images: list[str | dict]


class ImageSubjectSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_field: str
    images: MediaBinding

    @model_validator(mode="after")
    def validate_images(self) -> Self:
        if (
            self.images.kind != "image"
            or not self.images.array
            or self.images.external_sources_field is None
            or self.images.min_items != 1
        ):
            raise ValueError("主体槽位需要至少一张图片")
        return self


class ImageSubjectArray(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[ImageSubjectSlot] = Field(min_length=1, max_length=100)
    max_images: int = Field(gt=0, le=100)

    def sources(self, values: dict, bound: dict[str, dict]) -> list[ImageSubject]:
        subjects = []
        total_images = 0
        for index, slot in enumerate(self.slots, start=1):
            label = f"主体 {index}"
            subject_id = values.get(slot.id_field)
            subject_id = subject_id.strip() if isinstance(subject_id, str) else ""
            assets = slot.images.assets(label, bound)
            urls = slot.images.external_sources(
                label, values.get(slot.images.external_sources_field), alpha_requirement=None
            )
            count = len(assets) + len(urls)
            if not subject_id and not count:
                continue
            if not subject_id or not count:
                raise RunError(f"{label} 需要主体 ID 和至少一张图片", retryable=True)
            if count > len(slot.images.fields):
                raise RunError(f"{label} 最多 {len(slot.images.fields)} 张图片", retryable=True)
            subjects.append(ImageSubject(subject_id, [*assets, *urls]))
            total_images += count
        if not subjects:
            raise RunError("至少需要一个图片主体", retryable=True)
        if total_images > self.max_images:
            raise RunError(f"主体图片合计最多 {self.max_images} 张", retryable=True)
        return subjects


class AtlasSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=200)
    operation: Literal["image", "video", "audio"]
    base64_output_format: Literal["image", "zip"] = "image"
    prediction_timeout_seconds: int = Field(default=GENERATION_TIMEOUT_SECONDS, gt=0)
    prediction_endpoint: Literal["prediction", "result"] = "prediction"
    request_max_bytes: int | None = Field(default=None, gt=0)
    parameters: dict[str, str]
    parameter_overrides: dict[str, str] = Field(default_factory=dict)
    parameter_objects: dict[str, dict[str, str]] = Field(default_factory=dict)
    fixed: dict[str, JsonValue] = Field(default_factory=dict)
    required_text: list[str] = Field(default_factory=list)
    text_max_lengths: dict[str, Annotated[int, Field(gt=0)]] = Field(default_factory=dict)
    text_flag_suffix_parameters: set[str] = Field(default_factory=set)
    omit_blank_parameters: list[str] = Field(default_factory=list)
    public_url_parameters: list[str] = Field(default_factory=list)
    json_object_parameters: list[str] = Field(default_factory=list)
    lora_parameters: dict[str, Literal["weights", "array"] | LoRAArrayLimits] = Field(
        default_factory=dict
    )
    kling_storyboard_field: str | None = None
    kling_storyboard_encoding: Literal["integer_duration", "indexed_string_duration"] = (
        "integer_duration"
    )
    kling_elements: KlingElementArray | None = None
    kling_reference_limits: KlingReferenceLimits | None = None
    kling_max_total_inputs: int | None = Field(default=None, gt=0)
    kling_max_total_images: int | None = Field(default=None, gt=0)
    kling_max_total_video_duration_ms: int | None = Field(default=None, gt=0)
    composition_plan_field: str | None = None
    dialogue: DialogueBinding | None = None
    color_palette_field: str | None = None
    audio_suffix_parameter: str = "output_format"
    audio_suffixes: dict[str, Literal[".pcm", ".ulaw", ".alaw", ".opus"]] = Field(
        default_factory=dict
    )
    image_size_limits: ImageSizeLimits | None = None
    media: dict[str, MediaBinding | MediaObjectArray] = Field(default_factory=dict)
    max_media_items: int | None = Field(default=None, gt=0)
    image_aspect_ratio_match: ImageAspectRatioMatch | None = None
    image_subjects: ImageSubjectArray | None = None
    media_bitmask: MediaBitmask | None = None
    reference_arrays: dict[str, ReferenceArray | VideoKeyframes | ImageReferenceObjects] = Field(
        default_factory=dict
    )
    choice_arrays: dict[str, ChoiceArray | ChoiceSlots] = Field(default_factory=dict)
    choice_constraints: dict[str, ChoiceConstraint] = Field(default_factory=dict)
    choice_bounds: dict[str, ChoiceBounds | Annotated[list[ChoiceBounds], Field(min_length=1)]] = (
        Field(default_factory=dict)
    )
    text_arrays: dict[str, TextArray] = Field(default_factory=dict)
    enabled_by: dict[str, str | ParameterCondition] = Field(default_factory=dict)
    required_when: dict[str, ParameterConditions | list[ParameterConditions]] = Field(
        default_factory=dict
    )
    forbidden_combinations: list[Annotated[ParameterConditions, Field(min_length=2)]] = Field(
        default_factory=list
    )
    mutually_exclusive: list[tuple[str, str]] = Field(default_factory=list)
    required_one_of: list[tuple[str, str]] = Field(default_factory=list)
    required_any_of: list[Annotated[tuple[str, ...], Field(min_length=2)]] = Field(
        default_factory=list
    )
    media_requires_any_of: dict[str, Annotated[tuple[str, ...], Field(min_length=1)]] = Field(
        default_factory=dict
    )
    maximum_with_media: dict[str, dict[str, FiniteFloat | MediaParameterMaximum]] = Field(
        default_factory=dict
    )
    return_voice_result: bool = False

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        request_parameters = self.parameters.keys() | self.fixed.keys()
        input_parameters = (
            request_parameters
            | self.media.keys()
            | self.choice_arrays.keys()
            | self.text_arrays.keys()
        )
        names = input_parameters | self.parameter_objects.keys()
        controllers = {
            rule if isinstance(rule, str) else rule.parameter for rule in self.enabled_by.values()
        }
        size_parameters = set()
        if self.image_size_limits is not None:
            size_parameters.add(self.image_size_limits.parameter)
            if self.image_size_limits.auto_requires is not None:
                size_parameters.add(self.image_size_limits.auto_requires)
        if self.image_aspect_ratio_match is not None and any(
            not isinstance(binding, MediaBinding) or binding.kind != "image" or binding.array
            for binding in (
                self.media.get(name) for name in self.image_aspect_ratio_match.parameters
            )
        ):
            raise ValueError("宽高比配对须引用两个独立的图片参数")
        if (
            "model" in names
            or "model" in self.reference_arrays
            or (
                self.image_subjects is not None
                and ("subjects" in names or "subjects" in self.reference_arrays)
            )
            or self.reference_arrays.keys() & names
            or any(
                isinstance(binding, VideoKeyframes)
                and (
                    self.operation != "video"
                    or binding.duration_parameter not in request_parameters
                )
                for binding in self.reference_arrays.values()
            )
            or self.parameters.keys() & self.fixed.keys()
            or self.parameter_overrides.keys() - self.parameters.keys()
            or self.parameter_objects.keys() & (input_parameters - self.parameters.keys())
            or any(not fields for fields in self.parameter_objects.values())
            or self.media.keys() & request_parameters
            or self.choice_arrays.keys() & (request_parameters | self.media.keys())
            or self.text_arrays.keys()
            & (request_parameters | self.media.keys() | self.choice_arrays.keys())
            or self.enabled_by.keys() - names
            or controllers - request_parameters
            or self.enabled_by.keys() & controllers
            or set(self.required_text) - self.parameters.keys()
            or self.choice_constraints.keys() - self.parameters.keys()
            or any(
                constraint.parameter not in request_parameters
                for constraint in self.choice_constraints.values()
            )
            or self.choice_bounds.keys() - self.parameters.keys()
            or any(
                bounds.parameter not in request_parameters
                for rules in self.choice_bounds.values()
                for bounds in (rules if isinstance(rules, list) else [rules])
            )
            or self.required_when.keys() - (self.parameters.keys() | self.media.keys())
            or any(
                not clause or clause.keys() - request_parameters
                for rules in self.required_when.values()
                for clause in (rules if isinstance(rules, list) else [rules])
            )
            or any(clause.keys() - request_parameters for clause in self.forbidden_combinations)
            or any(
                left == right or {left, right} - names
                for left, right in self.mutually_exclusive + self.required_one_of
            )
            or any(
                len(set(group)) != len(group) or set(group) - names
                for group in self.required_any_of
            )
            or any(
                name in group or len(set(group)) != len(group) or {name, *group} - self.media.keys()
                for name, group in self.media_requires_any_of.items()
            )
            or self.maximum_with_media.keys() - self.media.keys()
            or any(
                not limits or limits.keys() - request_parameters
                for limits in self.maximum_with_media.values()
            )
            or (self.return_voice_result and self.operation != "audio")
            or self.text_max_lengths.keys() - self.parameters.keys()
            or self.text_flag_suffix_parameters - self.text_max_lengths.keys()
            or set(self.omit_blank_parameters) - self.parameters.keys()
            or set(self.public_url_parameters) - self.parameters.keys()
            or set(self.json_object_parameters) - self.parameters.keys()
            or self.lora_parameters.keys() - self.parameters.keys()
            or self.lora_parameters.keys() & set(self.json_object_parameters)
            or (
                self.kling_storyboard_field is not None
                and (
                    "multi_prompt" in names
                    or {"multi_shot", "prompt", "duration"} - request_parameters
                )
            )
            or (self.kling_elements is not None and "elements" in names)
            or (
                self.kling_reference_limits is not None
                and (
                    self.kling_storyboard_field is None
                    or self.kling_elements is None
                    or {"images", "video"} - self.media.keys()
                    or "sound" not in request_parameters
                )
            )
            or (
                self.composition_plan_field is not None
                and (
                    "composition_plan" in names
                    or {"prompt", "duration", "force_instrumental"} - request_parameters
                )
            )
            or (
                self.dialogue is not None
                and ("inputs" in names or {"text", "voice"} - request_parameters)
            )
            or (self.color_palette_field is not None and "color_palette" in names)
            or (
                self.audio_suffixes
                and (
                    self.operation != "audio"
                    or self.audio_suffix_parameter not in request_parameters
                )
            )
            or (self.image_size_limits is not None and size_parameters - request_parameters)
            or (
                self.media_bitmask is not None
                and (
                    self.media_bitmask.parameter not in self.parameters
                    or set(self.media_bitmask.media) - self.media.keys()
                    or len(set(self.media_bitmask.media)) != len(self.media_bitmask.media)
                )
            )
            or any(
                isinstance(binding, MediaBinding)
                and binding.count_parameter is not None
                and (
                    binding.count_parameter == name
                    or binding.count_parameter not in self.parameters.keys() | self.media.keys()
                )
                for name, binding in self.media.items()
            )
            or any(
                isinstance(binding, MediaBinding)
                and binding.format is not None
                and binding.format.parameter not in self.parameters
                for binding in self.media.values()
            )
            or any(
                isinstance(binding, MediaBinding)
                and binding.duration_choice is not None
                and binding.duration_choice.parameter not in request_parameters
                for binding in self.media.values()
            )
            or any(
                isinstance(binding, MediaBinding)
                and binding.alpha_for_background_parameter is not None
                and binding.alpha_for_background_parameter not in request_parameters
                for binding in self.media.values()
            )
            or any(
                isinstance(binding, MediaBinding)
                and binding.excluded_output_formats
                and "output_format" not in request_parameters
                for binding in self.media.values()
            )
        ):
            raise ValueError("Atlas 请求字段映射无效")
        return self

    def _parameter_enabled(self, name: str, payload: dict) -> bool:
        rule = self.enabled_by.get(name)
        if isinstance(rule, str):
            return payload.get(rule) is not False
        if rule is not None:
            if isinstance(rule.equals, list):
                return payload.get(rule.parameter) in rule.equals
            return payload.get(rule.parameter, rule.equals) == rule.equals
        return True

    @staticmethod
    def _matches_conditions(payload: dict, clause: ParameterConditions) -> bool:
        return all(
            payload.get(key) in expected
            if isinstance(expected, list)
            else payload.get(key, False) == expected
            for key, expected in clause.items()
        )

    def _parameter_required(self, name: str, payload: dict) -> bool:
        rules = self.required_when[name]
        return any(
            self._matches_conditions(payload, clause)
            for clause in (rules if isinstance(rules, list) else [rules])
        )

    def validate_request_size(self, payload: dict) -> None:
        if self.request_max_bytes is None:
            return
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if len(body) > self.request_max_bytes:
            raise RunError(f"Atlas Cloud 请求体最多 {self.request_max_bytes} 字节", retryable=True)

    def payload(self, values: dict) -> dict:
        mapped = {
            key: values[field]
            for key, field in self.parameters.items()
            if values.get(field) is not None
        }
        seed = mapped.get("seed")
        if isinstance(seed, str) and re.fullmatch(r"-?(0|[1-9][0-9]*)", seed):
            mapped["seed"] = int(seed)
        for key, field in self.parameter_overrides.items():
            value = values.get(field)
            if isinstance(value, str) and (value := value.strip()):
                mapped[key] = value
        for name in self.omit_blank_parameters:
            if isinstance(value := mapped.get(name), str) and not value.strip():
                del mapped[name]
        for name in self.required_text:
            if not isinstance(mapped.get(name), str) or not mapped[name].strip():
                raise RunError("请填写提示词" if name == "prompt" else "请填写文本", retryable=True)
        payload = {"model": self.model, **self.fixed, **mapped}
        for name, fields in self.parameter_objects.items():
            # An API may accept a scalar preset or an object with custom values.
            fields_by_parameter = {
                key: values[field] for key, field in fields.items() if values.get(field) is not None
            }
            if fields_by_parameter:
                payload[name] = fields_by_parameter
        if self.composition_plan_field is not None:
            _apply_composition_plan(payload, values.get(self.composition_plan_field))
        if self.dialogue is not None:
            self.dialogue.apply(payload, values)
        if self.color_palette_field is not None:
            palette = values.get(self.color_palette_field)
            if isinstance(palette, str) and palette.strip():
                payload["color_palette"] = _parse_color_palette(palette)
        if self.image_size_limits is not None:
            self.image_size_limits.validate_size(payload)
        if self.kling_storyboard_field is not None:
            _apply_kling_storyboard(
                payload,
                values.get(self.kling_storyboard_field),
                indexed=self.kling_storyboard_encoding == "indexed_string_duration",
            )
        if self.kling_elements is not None and (
            elements := self.kling_elements.items(values.get(self.kling_elements.field))
        ):
            payload["elements"] = elements
        for name, binding in self.choice_arrays.items():
            if isinstance(binding, ChoiceSlots):
                if items := binding.items(name, values):
                    payload[name] = items
                continue
            selected = [
                option.value for option in binding.options if values.get(option.field) is True
            ]
            if len(selected) < binding.min_items:
                raise RunError(f"{name} 至少选择 {binding.min_items} 个选项", retryable=True)
            if selected:
                payload[name] = (
                    ", ".join(selected) if binding.encoding == "comma_separated" else selected
                )
        for name, binding in self.text_arrays.items():
            if items := binding.items(name, values.get(binding.field)):
                payload[name] = items
        for name, binding in self.media.items():
            if not self._parameter_enabled(name, payload):
                continue
            if isinstance(binding, MediaObjectArray):
                if sources := binding.external_sources(name, values):
                    payload[name] = sources
            elif binding.ordered_source_fields:
                alpha_requirement = binding.alpha_requirement(name, payload)
                ordered_sources = []
                for field in binding.ordered_source_fields:
                    sources = binding.external_sources(
                        field, values.get(field), alpha_requirement=alpha_requirement, limit=1
                    )
                    ordered_sources.append(sources[0] if sources else None)
                if any(ordered_sources):
                    payload[name] = ordered_sources
            elif binding.external_sources_field is not None and (
                sources := binding.external_sources(
                    name,
                    values.get(binding.external_sources_field),
                    alpha_requirement=binding.alpha_requirement(name, payload),
                )
            ):
                payload[name] = sources if binding.array else sources[0]
        for name in self.enabled_by:
            if not self._parameter_enabled(name, payload):
                payload.pop(name, None)
        for name in self.public_url_parameters:
            if name not in payload:
                continue
            value = payload[name]
            if not isinstance(value, str) or not _web_url(value.strip(), schemes=("http", "https")):
                raise RunError(f"{name} 需要公开的 HTTP(S) 地址", retryable=True)
            payload[name] = value.strip()
        for name, constraint in self.choice_constraints.items():
            value = payload.get(name)
            selection = payload.get(constraint.parameter)
            expected = constraint.values.get(selection) if isinstance(selection, str) else None
            if isinstance(expected, bool):
                if value is not expected:
                    state = "开启" if expected else "关闭"
                    raise RunError(
                        f"当前选择的 {constraint.parameter} 要求{state} {name}", retryable=True
                    )
                continue
            if (
                isinstance(expected, str)
                and constraint.default_value is not None
                and value in (None, constraint.default_value)
            ):
                payload[name] = expected
                continue
            if not isinstance(value, str):
                continue
            if not (value := value.strip()):
                del payload[name]
                continue
            allowed = [expected] if isinstance(expected, str) else expected
            if allowed is not None and value not in allowed:
                raise RunError(
                    f"当前选择的 {constraint.parameter} 要求 {name} 为 {'、'.join(allowed)}",
                    retryable=True,
                )
            payload[name] = value
        for name, rules in self.choice_bounds.items():
            for bounds in rules if isinstance(rules, list) else [rules]:
                bounds.validate_value(name, payload)
        for clause in self.forbidden_combinations:
            if self._matches_conditions(payload, clause):
                raise RunError(
                    f"Atlas Cloud 不支持当前 {'、'.join(clause)} 参数组合", retryable=True
                )
        for name in self.required_when:
            if name in self.media:
                continue
            value = payload.get(name)
            if value is not None and (not isinstance(value, str) or value.strip()):
                continue
            if self._parameter_required(name, payload):
                raise RunError(f"当前设置需要填写 {name}", retryable=True)
        for name, limit in self.text_max_lengths.items():
            text = payload.get(name)
            if isinstance(text, str) and name in self.text_flag_suffix_parameters:
                text = re.split(r"(?:^|\s+)--[A-Za-z][A-Za-z0-9-]*(?=\s|$)", text, maxsplit=1)[0]
                if name in self.required_text and not text.strip():
                    raise RunError("请填写提示词", retryable=True)
            if text is not None and (not isinstance(text, str) or len(text) > limit):
                raise RunError(f"{name} 最多 {limit} 个字符", retryable=True)
        for pair in self.required_one_of + self.required_any_of:
            for name in pair:
                if isinstance(value := payload.get(name), str):
                    if normalized := value.strip():
                        payload[name] = normalized
                    else:
                        payload.pop(name, None)
        for name in self.json_object_parameters:
            if name not in payload:
                continue
            value = payload[name]
            if isinstance(value, str) and not value.strip():
                del payload[name]
                continue
            try:
                if not isinstance(value, str) or not isinstance(json.loads(value), dict):
                    raise ValueError()
            except (ValueError, RecursionError):
                raise RunError(f"{name} 需要 JSON 对象文本", retryable=True) from None
        for name, shape in self.lora_parameters.items():
            if name in payload:
                payload[name] = _parse_lora_list(name, payload[name], shape)
        return payload

    def assets_by_parameter(self, payload: dict, bound: dict[str, dict]) -> dict[str, list[dict]]:
        result = {}
        counts = {}
        for name, binding in self.media.items():
            if not self._parameter_enabled(name, payload):
                continue
            if isinstance(binding, MediaObjectArray):
                external_objects = payload.get(name, [])
                assets = binding.assets(name, bound, external_objects)
                if assets:
                    result[name] = assets
                counts[name] = len(assets) + len(external_objects)
                continue
            external = payload.get(name) if binding.has_external_sources else None
            if (
                binding.ordered_source_fields
                and external is not None
                and any(
                    source is not None and field in bound
                    for field, source in zip(binding.fields, external, strict=True)
                )
            ):
                raise RunError(f"{name} 每个素材槽位只能选择一种来源", retryable=True)
            external_count = (
                sum(source is not None for source in external)
                if isinstance(external, list)
                else int(isinstance(external, str))
            )
            assets = binding.assets(
                name,
                bound,
                min_items=0 if binding.has_external_sources else binding.min_items,
                duration_cap_ms=binding.duration_choice.cap(payload)
                if binding.duration_choice
                else None,
            )
            total = len(assets) + external_count
            counts[name] = total
            maximum = binding.max_sources
            if binding.has_external_sources and not (
                binding.min_items <= total and (maximum is None or total <= maximum)
            ):
                count = f"至少 {binding.min_items}" if maximum is None else str(binding.min_items)
                if maximum is not None and binding.min_items != maximum:
                    count += f" 至 {maximum}"
                raise RunError(f"{name} 需要 {count} {binding.source_unit}", retryable=True)
            if total and payload.get("output_format") in binding.excluded_output_formats:
                raise RunError(f"{name} 不可与 {payload['output_format']} 一起使用", retryable=True)
            alpha_requirement = binding.alpha_requirement(name, payload)
            if (
                alpha_requirement
                and (total or binding.alpha_for_background_parameter)
                and (total != 1 or (assets and assets[0].get("contentType") != "image/png"))
            ):
                raise RunError(alpha_requirement, retryable=True)
            if not assets:
                continue
            binding.validate_pixel_count_ratio(name, assets)
            if binding.format is not None:
                selected = payload.get(binding.format.parameter, binding.format.default)
                if isinstance(selected, str):
                    types = binding.format.content_types.get(selected)
                    allowed = [types] if isinstance(types, str) else types
                    if allowed and any(asset.get("contentType") not in allowed for asset in assets):
                        raise RunError(f"{name} 的文件格式须与 {selected} 一致", retryable=True)
            result[name] = assets
        if self.image_aspect_ratio_match is not None:
            self.image_aspect_ratio_match.validate_assets(result)
        if self.max_media_items is not None and sum(counts.values()) > self.max_media_items:
            raise RunError(f"素材合计最多 {self.max_media_items} 项", retryable=True)
        for name, binding in self.media.items():
            if (
                not isinstance(binding, MediaBinding)
                or binding.max_combined is None
                or binding.count_parameter is None
                or name not in counts
            ):
                continue
            linked = binding.count_parameter
            limit = binding.max_combined
            if linked in self.media:
                if counts[name] + counts.get(linked, 0) > limit:
                    raise RunError(f"{name} 和 {linked} 合计最多 {limit} 份素材", retryable=True)
            elif counts[name]:
                count = payload.get(linked)
                if type(count) is not int or count < 1:
                    raise RunError("请选择有效的生成数量", retryable=True)
                if counts[name] + count > limit:
                    raise RunError(f"素材和生成数量合计最多 {limit}", retryable=True)
        for name in self.required_when:
            if (
                name in self.media
                and not counts.get(name)
                and self._parameter_required(name, payload)
            ):
                raise RunError(f"当前设置至少需要一份 {name} 素材", retryable=True)
        for left, right in self.mutually_exclusive:
            if (left in result or payload.get(left)) and (right in result or payload.get(right)):
                raise RunError(f"{left} 和 {right} 请任选其一", retryable=True)
        for left, right in self.required_one_of:
            if (left in result or left in payload) == (right in result or right in payload):
                raise RunError(f"{left} 和 {right} 必须选择一项", retryable=True)
        for group in self.required_any_of:
            if not any(name in result or payload.get(name) for name in group):
                raise RunError(f"{' 和 '.join(group)} 至少需要一项", retryable=True)
        for name, group in self.media_requires_any_of.items():
            if counts.get(name) and not any(counts.get(source) for source in group):
                raise RunError(f"使用 {name} 时，{' 和 '.join(group)} 至少需要一项", retryable=True)
        for name, limits in self.maximum_with_media.items():
            count = counts.get(name, 0)
            if not count:
                continue
            for parameter, limit in limits.items():
                if isinstance(limit, MediaParameterMaximum):
                    if count < limit.min_items:
                        continue
                    maximum = limit.maximum
                    source = f"至少 {limit.min_items} 份 {name}"
                else:
                    maximum = limit
                    source = name
                value = payload.get(parameter)
                if value is not None and (type(value) not in (int, float) or value > maximum):
                    raise RunError(
                        f"使用 {source} 时 {parameter} 最大为 {maximum:g}", retryable=True
                    )
        if self.media_bitmask is not None:
            self.media_bitmask.validate_request(payload, result)
        if self.kling_reference_limits is not None:
            self.kling_reference_limits.apply(payload, counts)
        if self.kling_max_total_inputs is not None:
            total = (
                sum(counts.values())
                + len(payload.get("elements", []))
                + len(payload.get("voice_ids", []))
            )
            if total > self.kling_max_total_inputs:
                raise RunError(
                    f"图片、视频、主体和音色合计最多 {self.kling_max_total_inputs} 项",
                    retryable=True,
                )
        if self.kling_max_total_images is not None:
            images = sum(
                counts.get(parameter, 0)
                for parameter in ("image", "middle_images", "last_image", "reference_images")
            )
            if images > self.kling_max_total_images:
                raise RunError(
                    f"关键帧和参考图合计最多 {self.kling_max_total_images} 张",
                    retryable=True,
                )
        if self.kling_max_total_video_duration_ms is not None:
            duration = sum(
                milliseconds
                for parameter in ("video", "reference_videos")
                for asset in result.get(parameter, [])
                if (milliseconds := _asset_duration(parameter, asset)) is not None
            )
            if duration > self.kling_max_total_video_duration_ms:
                raise RunError(
                    f"原视频与参考视频合计最长 {self.kling_max_total_video_duration_ms} 毫秒",
                    retryable=True,
                )
        return result


def _data(response: httpx.Response) -> dict:
    result = response.raise_for_status().json()
    if isinstance(result, dict):
        if isinstance(data := result.get("data"), dict):
            return data
        if (
            "data" not in result
            and isinstance(result.get("id"), str)
            and isinstance(result.get("status"), str)
        ):
            return result
    raise ValueError("Atlas Cloud response has no data")


def _web_url(value: object, *, schemes: tuple[str, ...]) -> TypeGuard[str]:
    if not isinstance(value, str):
        return False
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL:
        return False
    return url.scheme in schemes and bool(url.host) and not url.userinfo


def _https_url(value: object) -> TypeGuard[str]:
    return _web_url(value, schemes=("https",))


def png_has_alpha(stream: BinaryIO) -> bool:
    header = stream.read(33)
    if len(header) != 33 or not header.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"):
        return False
    if header[25] in {4, 6}:
        return True
    while len(chunk := stream.read(8)) == 8:
        length, kind = int.from_bytes(chunk[:4], "big"), chunk[4:]
        if kind == b"tRNS":
            return length > 0 and len(stream.read(1)) == 1
        if kind in {b"IDAT", b"IEND"}:
            break
        stream.seek(length + 4, 1)
    return False


@dataclass(frozen=True)
class InlineOutput:
    content: bytes
    suffix: str


@dataclass(frozen=True)
class RemoteOutput:
    url: str
    filename: str


def _inline_image_type(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if content.startswith(b"BM"):
        return "image/bmp", ".bmp"
    if content.startswith((b"II\x2a\x00", b"MM\x00\x2a")):
        return "image/tiff", ".tiff"
    if content[4:8] == b"ftyp":
        brand = content[8:12]
        if brand in {b"heic", b"heix", b"hevc", b"hevx"}:
            return "image/heic", ".heic"
        if brand in {b"mif1", b"msf1"}:
            return "image/heif", ".heif"
    return None


def _inline_mp4_container(content: bytes) -> bool:
    box_size = int.from_bytes(content[:4], "big")
    return (
        content[4:8] == b"ftyp"
        and 16 <= box_size <= min(len(content), 4096)
        and box_size % 4 == 0
        and _inline_image_type(content) is None
    )


def _inline_video_type(content: bytes) -> str | None:
    if content.startswith(b"\x1a\x45\xdf\xa3") and b"\x42\x82\x84webm" in content[:4096]:
        return "video/webm"
    if _inline_mp4_container(content):
        brand = content[8:12]
        if brand == b"qt  ":
            return "video/quicktime"
        if brand not in {b"M4A ", b"M4B ", b"M4P ", b"M4R "}:
            return "video/mp4"
    return None


def _inline_audio_type(content: bytes) -> Literal["m4a", "mp3", "ogg", "wav"] | None:
    if content.startswith((b"RIFF", b"RF64", b"RIFX")) and content[8:12] == b"WAVE":
        return "wav"
    if _inline_mp4_container(content):
        return "m4a"
    if content.startswith(b"OggS\x00"):
        return "ogg"
    if content.startswith(b"ID3") or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    ):
        return "mp3"
    return None


def _inline_output(value: object, output_format: Base64Format) -> InlineOutput:
    if output_format == "zip":
        invalid = "Atlas Cloud 返回的 Base64 ZIP 无效"
        headers = {"data:application/zip;base64", "data:application/octet-stream;base64"}
    elif output_format == "mp4":
        invalid = "Atlas Cloud 返回的 Base64 视频无效"
        headers = {"data:video/mp4;base64", "data:application/octet-stream;base64"}
    elif audio_types := INLINE_AUDIO_CONTENT_TYPES.get(output_format):
        invalid = "Atlas Cloud 返回的 Base64 音频无效"
        headers = {f"data:{mime};base64" for mime in (*audio_types, "application/octet-stream")}
    else:
        invalid = "Atlas Cloud 返回的 Base64 图像无效"
        headers = {
            "data:image/png;base64",
            "data:image/jpeg;base64",
            "data:image/webp;base64",
            "data:image/gif;base64",
        }
    if not isinstance(value, str):
        raise RunError(invalid)
    encoded = value
    if value.startswith("data:"):
        header, separator, encoded = value.partition(",")
        if not separator or header.lower() not in headers:
            raise RunError(invalid)
    if len(encoded) > 4 * ((MAX_INLINE_OUTPUT_BYTES + 2) // 3):
        raise RunError("文件超过工作机允许的大小")
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise RunError(invalid) from None
    if len(content) > MAX_INLINE_OUTPUT_BYTES:
        raise RunError("文件超过工作机允许的大小")
    if output_format in INLINE_AUDIO_CONTENT_TYPES:
        valid = (
            bool(content) and len(content) % 2 == 0
            if output_format == "pcm"
            else _inline_audio_type(content) == output_format
        )
        if not valid:
            raise RunError(invalid)
        return InlineOutput(content, "." + output_format)
    if output_format == "zip":
        if not content.startswith(b"PK\x03\x04"):
            raise RunError(invalid)
        return InlineOutput(content, ".zip")
    if output_format == "mp4":
        if not _inline_mp4_container(content):
            raise RunError(invalid)
        return InlineOutput(content, ".mp4")
    if image_type := _inline_image_type(content):
        return InlineOutput(content, image_type[1])
    raise RunError(invalid)


def _text_outputs(data: dict) -> list[str | InlineOutput | RemoteOutput] | None:
    outputs = data.get("outputs")
    result, text_key = data.get("lyrics_result"), "lyrics"
    if not isinstance(result, dict):
        result, text_key = data.get("stt_result"), "text"
    details = result if isinstance(result, dict) else None
    text = details.get(text_key) if details is not None else None
    channels = details.get("channels") if details is not None else None
    if not isinstance(text, str) and isinstance(channels, list) and channels:
        text = "\n\n".join(
            channel["text"]
            for channel in channels
            if isinstance(channel, dict) and isinstance(channel.get("text"), str)
        )
    if not isinstance(text, str) and isinstance(outputs, list):
        items = [item for item in outputs if isinstance(item, str)]
        text = "\n\n".join(items) if items else None
    if not isinstance(text, str):
        return None
    try:
        content = (text or "\n").encode("utf-8")
    except UnicodeError:
        raise RunError("Atlas Cloud 返回的文本成品无效") from None
    files: list[str | InlineOutput | RemoteOutput] = [InlineOutput(content, ".txt")]
    if details is not None:
        files.append(_json_output(details))
    return files


def _json_output(details: dict) -> InlineOutput:
    try:
        content = json.dumps(details, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        return InlineOutput((content + "\n").encode("utf-8"), ".json")
    except (ValueError, RecursionError):
        raise RunError("Atlas Cloud 返回的文本成品无效") from None


def _completed_outputs(
    data: dict,
    *,
    inline_format: InlineFormat | None,
    include_metadata: bool,
    return_voice_result: bool,
    include_thumbnail: bool,
    draft_prediction_id: str | None,
) -> list[str | InlineOutput | RemoteOutput] | None:
    status = data.get("status")
    if status == "timeout":
        raise RunError("Atlas Cloud 生成超时", retryable=True)
    if status in ("failed", "cancelled", "canceled"):
        raise RunError("Atlas Cloud 未能完成生成", retryable=True)
    if status not in ("completed", "succeeded"):
        return None
    if inline_format == "text":
        return _text_outputs(data)
    outputs = data.get("outputs", data.get("output"))
    voice = data.get("voice_result") if return_voice_result else None
    if return_voice_result and not isinstance(voice, dict):
        return None
    if isinstance(voice, dict) and not outputs and _https_url(trial := voice.get("trial_url")):
        outputs = [trial]
    if not isinstance(outputs, list) or not outputs:
        logger.debug("等待 Atlas Cloud 提供成品地址")
        return None
    filenames = {}
    metadata_urls = []
    files = data.get("files")
    if isinstance(files, list):
        for index, item in enumerate(files, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            filename = item.get("file_name")
            name = ""
            if isinstance(filename, str):
                basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
                if (
                    1 <= len(basename) <= 200
                    and basename not in {".", ".."}
                    and basename.isprintable()
                ):
                    name = basename
            kind = item.get("type")
            if include_metadata and kind == "METADATA" and _https_url(item["url"]):
                name = Path(name or f"result-{index}").with_suffix(".json").name
                if item["url"] not in outputs and item["url"] not in metadata_urls:
                    metadata_urls.append(item["url"])
            suffix = MODEL_OUTPUT_SUFFIXES.get(kind) if isinstance(kind, str) else None
            if suffix and not Path(name).suffix:
                name = (name[: 200 - len(suffix)] or f"result-{index}") + suffix
            if name:
                filenames[item["url"]] = name
    result: list[str | InlineOutput | RemoteOutput] = []
    for value in [*outputs, *metadata_urls]:
        if _https_url(value):
            result.append(RemoteOutput(value, filenames[value]) if value in filenames else value)
        elif inline_format is not None:
            result.append(_inline_output(value, inline_format))
        else:
            raise RunError("Atlas Cloud 返回的成品地址无效")
    if isinstance(voice, dict):
        voice_id = voice.get("voice_id")
        if not isinstance(voice_id, str) or not re.fullmatch(r"[0-9]{18}", voice_id):
            raise RunError("Atlas Cloud 返回的音色 ID 无效")
        result.extend(
            (InlineOutput((voice_id + "\n").encode("utf-8"), ".txt"), _json_output(voice))
        )
    if include_metadata:
        image_metadata = {
            key: items
            for key in ("layers", "image_results")
            if isinstance(items := data.get(key), list) and items
        }
        if image_metadata:
            result.append(_json_output(image_metadata))
    if draft_prediction_id is not None:
        draft_id = data.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id.strip() or not draft_id.isprintable():
            draft_id = draft_prediction_id
        result.append(InlineOutput((draft_id + "\n").encode("utf-8"), ".txt"))
    if (
        include_thumbnail
        and _https_url(thumbnail := data.get("thumbnail"))
        and thumbnail not in outputs
    ):
        result.append(thumbnail)
    return result


class Atlas:
    def __init__(self, client: httpx.AsyncClient, *, poll_seconds: float = 3) -> None:
        self.client = client
        self.poll_seconds = poll_seconds

    async def upload(self, file: Path | BinaryIO, filename: str, content_type: str) -> str:
        try:
            with file.open("rb") if isinstance(file, Path) else nullcontext(file) as source:
                response = await self.client.post(
                    "uploadMedia", files={"file": (filename, source, content_type)}
                )
            logger.debug("Atlas Cloud 素材上传响应", http_status=response.status_code)
            result = response.raise_for_status().json()
            if isinstance(result, dict):
                url = result.get("url")
                if _https_url(url):
                    return url
                if isinstance(data := result.get("data"), dict):
                    for field in ("url", "download_url"):
                        if _https_url(url := data.get(field)):
                            return url
            logger.debug("Atlas Cloud 素材上传响应缺少有效地址")
        except (httpx.HTTPError, ValueError) as error:
            logger.debug("Atlas Cloud 素材上传未完成", error_type=type(error).__name__)
        raise RunError("素材上传到 Atlas Cloud 失败", retryable=True)

    async def calculate(self, payload: dict) -> tuple[Decimal, bool]:
        response = await self.client.post("calculate", json=payload, timeout=10)
        result = response.raise_for_status().json(parse_float=Decimal)
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            raise ValueError("Atlas Cloud 报价缺少 data")
        raw_price = data.get("price")
        estimated = data.get("estimated", False)
        if isinstance(raw_price, bool) or not isinstance(raw_price, (int, str, Decimal)):
            raise ValueError("Atlas Cloud 报价缺少有效金额")
        try:
            price = Decimal(raw_price)
        except InvalidOperation:
            raise ValueError("Atlas Cloud 报价缺少有效金额") from None
        if not price.is_finite() or price < 0 or not isinstance(estimated, bool):
            raise ValueError("Atlas Cloud 报价缺少有效金额")
        return price, estimated

    async def submit(self, spec: AtlasSpec, payload: dict) -> tuple[str, dict]:
        endpoint = {
            "image": "generateImage",
            "video": "generateVideo",
            "audio": "generateAudio",
        }[spec.operation]
        timeout = self.client.timeout
        if payload.get("enable_sync_mode") is True:
            timeout = httpx.Timeout(
                connect=timeout.connect,
                read=GENERATION_TIMEOUT_SECONDS,
                write=timeout.write,
                pool=timeout.pool,
            )
        try:
            response = await self.client.post(endpoint, json=payload, timeout=timeout)
            logger.debug(
                "Atlas Cloud 生成提交响应", endpoint=endpoint, http_status=response.status_code
            )
            data = _data(response)
            prediction_id = data.get("id")
            if (
                isinstance(prediction_id, str)
                and 1 <= len(prediction_id) <= 64
                and prediction_id.isascii()
                and all(char.isalnum() or char in "_-" for char in prediction_id)
            ):
                return prediction_id, data
            logger.debug("Atlas Cloud 生成响应缺少有效编号")
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if 400 <= status < 500 and status != 408:
                raise RunError(
                    f"Atlas Cloud 拒绝了生成请求（HTTP {status}）", retryable=True
                ) from None
        except (httpx.RequestError, ValueError) as error:
            logger.debug("Atlas Cloud 生成提交未确认", error_type=type(error).__name__)
        raise RunError(SUBMISSION_UNKNOWN)

    async def outputs(
        self,
        prediction_id: str,
        *,
        inline_format: InlineFormat | None = None,
        initial: dict | None = None,
        timeout_seconds: int = GENERATION_TIMEOUT_SECONDS,
        prediction_endpoint: Literal["prediction", "result"] = "prediction",
        include_metadata: bool = False,
        return_voice_result: bool = False,
        include_thumbnail: bool = False,
        include_draft_id: bool = False,
    ) -> list[str | InlineOutput | RemoteOutput]:
        draft_prediction_id = prediction_id if include_draft_id else None
        try:
            async with asyncio.timeout(timeout_seconds):
                if initial is not None:
                    if completed := _completed_outputs(
                        initial,
                        inline_format=inline_format,
                        include_metadata=include_metadata,
                        return_voice_result=return_voice_result,
                        include_thumbnail=include_thumbnail,
                        draft_prediction_id=draft_prediction_id,
                    ):
                        return completed
                return await self._poll(
                    prediction_id,
                    prediction_endpoint=prediction_endpoint,
                    inline_format=inline_format,
                    include_metadata=include_metadata,
                    return_voice_result=return_voice_result,
                    include_thumbnail=include_thumbnail,
                    draft_prediction_id=draft_prediction_id,
                )
        except TimeoutError:
            raise RunError("等待 Atlas Cloud 成品超时，请核实生成结果") from None

    async def _poll(
        self,
        prediction_id: str,
        *,
        prediction_endpoint: Literal["prediction", "result"],
        inline_format: InlineFormat | None,
        include_metadata: bool,
        return_voice_result: bool,
        include_thumbnail: bool,
        draft_prediction_id: str | None,
    ) -> list[str | InlineOutput | RemoteOutput]:
        previous_status = None
        while True:
            try:
                data = _data(await self.client.get(f"{prediction_endpoint}/{prediction_id}"))
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                logger.debug("Atlas Cloud 轮询响应", http_status=status)
                if prediction_endpoint == "result" and status in {404, 405}:
                    prediction_endpoint = "prediction"
                    continue
                if status < 500 and status not in {408, 429}:
                    raise RunError(f"读取 Atlas Cloud 生成结果失败（HTTP {status}）") from None
            except (httpx.RequestError, ValueError) as error:
                logger.debug("Atlas Cloud 轮询未完成", error_type=type(error).__name__)
            else:
                prediction_status = data.get("status")
                logged_status = (
                    prediction_status
                    if isinstance(prediction_status, str)
                    and prediction_status in LOGGED_PREDICTION_STATUSES
                    else "unknown"
                )
                write_log = logger.debug if logged_status == previous_status else logger.info
                write_log("Atlas Cloud 生成状态", status=logged_status)
                previous_status = logged_status
                if completed := _completed_outputs(
                    data,
                    inline_format=inline_format,
                    include_metadata=include_metadata,
                    return_voice_result=return_voice_result,
                    include_thumbnail=include_thumbnail,
                    draft_prediction_id=draft_prediction_id,
                ):
                    return completed
            await asyncio.sleep(self.poll_seconds)
