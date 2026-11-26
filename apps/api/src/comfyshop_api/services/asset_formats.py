"""工作流表单与任务提交共用的本地素材格式。"""

from collections.abc import Sequence

from comfyshop_api.services.media_records import media_kind
from comfyshop_media.model_exports import GLB_CONTENT_TYPE
from comfyshop_media.uploads import ASSET_UPLOAD_CONTENT_TYPES

_DEFAULT_CONTENT_TYPES = {
    "image": ("image/png", "image/jpeg", "image/webp", "image/gif"),
    "video": ("video/mp4", "video/webm"),
    "audio": ("audio/flac",),
    "3d": (GLB_CONTENT_TYPE,),
}

# 选择器可以识别这些别名，平台入库时使用右侧的规范 MIME。
_CONTENT_TYPE_ALIASES = {
    "audio/mp3": "audio/mpeg",
    "audio/wave": "audio/wav",
    "audio/x-wav": "audio/wav",
    "video/quicktime": "video/mp4",
    "video/x-m4v": "video/mp4",
}


def asset_content_types(kinds: Sequence[str], declared: list[str] | None = None) -> list[str]:
    if declared is None:
        return [mime for kind in kinds for mime in _DEFAULT_CONTENT_TYPES[kind]]
    return [
        mime
        for mime in dict.fromkeys(declared)
        if media_kind(mime) in kinds
        and (mime in ASSET_UPLOAD_CONTENT_TYPES or _CONTENT_TYPE_ALIASES.get(mime) in declared)
    ]


def atlas_asset_content_types(execution: dict[str, object]) -> dict[str, list[str]]:
    """从现有素材槽位的字段名和 content_types 解析上传名单。"""
    config = execution.get("config")
    if execution.get("adapter") != "atlas-cloud" or not isinstance(config, dict):
        return {}
    pending: list[object] = [config.get("image_subjects")]
    for section in ("media", "reference_arrays"):
        if isinstance(bindings := config.get(section), dict):
            pending.extend(bindings.values())

    by_field: dict[str, list[str]] = {}
    while pending:
        binding = pending.pop()
        if isinstance(binding, list):
            pending.extend(binding)
        if not isinstance(binding, dict):
            continue
        pending.extend(
            binding[key] for key in ("groups", "slots", "asset", "images") if key in binding
        )
        fields = binding.get("fields")
        declared = binding.get("content_types")
        if not isinstance(fields, list) or not isinstance(declared, list) or not declared:
            continue
        formats = [mime for mime in declared if isinstance(mime, str)]
        for field in fields:
            if isinstance(field, str):
                by_field[field] = formats
    return by_field
