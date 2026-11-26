"""Use the same Atlas Cloud media bindings for generation and quotes."""

import asyncio
import base64
from collections.abc import Awaitable
from typing import BinaryIO, Literal, Protocol

from comfyshop_worker_protocol.logging import logger

from .atlas_cloud import (
    Atlas,
    AtlasSpec,
    MediaBinding,
    MediaObjectArray,
    RunError,
    VideoKeyframes,
    png_has_alpha,
)

MediaEncoding = Literal["url", "base64", "base64-data"]


class MediaReference(Protocol):
    def __call__(
        self,
        asset: dict,
        *,
        encoding: MediaEncoding,
        alpha_requirement: str | None = None,
        reject_png_alpha: bool = False,
    ) -> Awaitable[str]: ...


async def atlas_media_reference(
    atlas: Atlas,
    asset: dict,
    source: BinaryIO,
    *,
    encoding: MediaEncoding,
    alpha_requirement: str | None = None,
    reject_png_alpha: bool = False,
) -> str:
    if alpha_requirement or (reject_png_alpha and asset["contentType"] == "image/png"):
        has_alpha = await asyncio.to_thread(png_has_alpha, source)
        source.seek(0)
        if alpha_requirement and not has_alpha:
            raise RunError(alpha_requirement, retryable=True)
        if reject_png_alpha and asset["contentType"] == "image/png" and has_alpha:
            raise RunError("上传的 PNG 不得包含透明通道", retryable=True)
    if encoding == "url":
        return await atlas.upload(source, asset["filename"], asset["contentType"])
    data = await asyncio.to_thread(source.read)
    encoded = base64.b64encode(data).decode("ascii")
    return encoded if encoding == "base64-data" else f"data:{asset['contentType']};base64,{encoded}"


async def bind_atlas_media(
    spec: AtlasSpec,
    payload: dict,
    values: dict,
    assets: list[dict],
    reference: MediaReference,
) -> None:
    bound = {asset["inputName"]: asset for asset in assets}
    media = spec.assets_by_parameter(payload, bound)
    subjects = spec.image_subjects.sources(values, bound) if spec.image_subjects else []
    clips = {
        name: binding.video_clip.settings(values)
        for name, binding in spec.media.items()
        if isinstance(binding, MediaBinding)
        and binding.video_clip is not None
        and (name in media or name in payload)
    }
    reference_sources = {
        name: binding.sources(name, values, bound, payload)
        if isinstance(binding, VideoKeyframes)
        else binding.sources(name, values, bound)
        for name, binding in spec.reference_arrays.items()
    }
    for name, inputs in media.items():
        logger.debug("正在准备素材", parameter=name, asset_count=len(inputs))
        binding = spec.media[name]
        encoding = binding.encoding if isinstance(binding, MediaBinding) else "url"
        alpha_requirement = (
            binding.alpha_requirement(name, payload) if isinstance(binding, MediaBinding) else None
        )
        reject_png_alpha = (
            any(group.reject_png_alpha for group in binding.groups)
            if isinstance(binding, MediaObjectArray)
            else binding.reject_png_alpha
        )
        references = [
            await reference(
                asset,
                encoding=encoding,
                alpha_requirement=alpha_requirement,
                reject_png_alpha=reject_png_alpha,
            )
            for asset in inputs
        ]
        if isinstance(binding, MediaObjectArray):
            items = [
                {"url": url, "type": asset["media"]["kind"]}
                for url, asset in zip(references, inputs, strict=True)
            ]
            payload[name] = [*items, *payload.get(name, [])]
        elif binding.ordered_source_fields:
            slots = payload.get(name, [None] * len(binding.fields))
            uploads = iter(references)
            payload[name] = [source if source is not None else next(uploads) for source in slots]
        else:
            payload[name] = (
                [*references, *payload.get(name, [])] if binding.array else references[0]
            )
    for name, settings in clips.items():
        payload[name] = [{"url": url, **settings} for url in payload[name]]
    for name, sources in reference_sources.items():
        if sources:
            payload[name] = [
                {
                    **source.properties,
                    source.key: source.value
                    if isinstance(source.value, str)
                    else await reference(
                        source.value, encoding="base64-data" if source.inline else "url"
                    ),
                }
                for source in sources
            ]
    if subjects:
        payload["subjects"] = [
            {
                "id": subject.id,
                "images": [
                    image if isinstance(image, str) else await reference(image, encoding="url")
                    for image in subject.images
                ],
            }
            for subject in subjects
        ]
