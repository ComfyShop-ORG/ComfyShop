"""把工作流版本与工作机目录编成网页表单，再将用户输入冻结为可执行的任务快照。"""

import hashlib
import json
import math
import sys
from collections.abc import Sequence
from copy import deepcopy
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, DecimalException, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from comfyshop_api.core.i18n import SOURCE_LANGUAGE, localize, message_from_text, msg
from comfyshop_api.models import Asset, Machine, TaskAsset, WorkAsset, WorkflowVersion
from comfyshop_api.schemas import (
    MAX_TEXT_INPUT_LENGTH,
    MEDIA_INPUT_KINDS,
    AssetReference,
    InputValue,
    NodeCatalog,
    NodeInput,
    OfficialInput,
    ParameterSlider,
    RecordedInput,
    ScalarInput,
    WorkflowForm,
    WorkflowFormData,
    WorkflowInput,
    WorkflowParameterControls,
    WorkflowParameterDisplay,
    WorkflowParameterPresentation,
)
from comfyshop_api.security import owned_record
from comfyshop_api.services.asset_formats import asset_content_types, atlas_asset_content_types
from comfyshop_api.services.connections import matched
from comfyshop_api.services.parameter_features import (
    MASK_NODE,
    OUTPAINT_LABELS,
    OUTPAINT_NODE,
    image_crops_for,
    native_mask_nodes,
    output_sizes_for,
    parameter_presentation_for,
    reference_timelines_for,
    validate_reference_timelines,
)
from comfyshop_api.services.worker_types import worker_type

MAX_SAFE_INTEGER = 2**53 - 1
SEED_INPUT_NAMES = {"seed", "noise_seed"}

LABELS = {
    "text": "提示词",
    "prompt": "提示词",
    "text_g": "提示词",
    "text_l": "提示词",
    "negative_prompt": "负向提示词",
    "image": "参考图",
    "video": "参考视频",
    "file": "参考视频",
    "video_path": "参考视频",
    "audio": "参考音频",
    "model_file": "参考模型",
    "seed": "随机种子",
    "noise_seed": "随机种子",
    "steps": "步数",
    "cfg": "引导强度",
    "denoise": "降噪强度",
    "width": "宽度",
    "height": "高度",
    "batch_size": "批量大小",
    "sampler_name": "采样器",
    "scheduler": "调度器",
    "unet_name": "扩散模型",
    "ckpt_name": "模型",
    "clip_name": "文本编码器",
    "vae_name": "VAE",
    "lora_name": "LoRA",
    "weight_dtype": "权重精度",
    "aspect_ratio": "画面比例",
    "megapixels": "像素规模",
    "strength": "强度",
    "strength_model": "模型强度",
    "strength_clip": "文本强度",
    "guidance": "引导强度",
    "shift": "偏移",
    "length": "帧数",
    "frame_rate": "帧率",
    "fps": "帧率",
    "upscale_method": "放大方式",
    "scale_by": "放大倍数",
    "filename_prefix": "文件名前缀",
}


ASSET_PLACEHOLDER_PREFIX = "__comfyshop_asset__:"


def _is_seed(kind: str, name: str) -> bool:
    return kind == "integer" and name in SEED_INPUT_NAMES


PROMPT_INPUT_NAMES = {"text", "prompt", "text_g", "text_l"}


def _negative_prompt_nodes(graph: dict) -> set[str]:
    """返回接在采样节点 `negative` 输入上的节点 ID，它们的文本输入是负向提示词。"""
    return {
        node["inputs"]["negative"][0]
        for node in graph.values()
        if isinstance(node.get("inputs", {}).get("negative"), list)
        and len(node["inputs"]["negative"]) == 2
        and isinstance(node["inputs"]["negative"][0], str)
    }


def _prompt_sources(graph: dict, negatives: set[str]) -> tuple[set[str], set[str]]:
    """返回输出直接接到提示词输入的文本源节点，依次为正向和负向。

    只认没有任何连接输入的节点，例如多行文本原语。它们的文本字段就是用户要写的提示词。
    """
    positive: set[str] = set()
    negative: set[str] = set()
    for node_id, node in graph.items():
        for name, value in node.get("inputs", {}).items():
            if (
                name in PROMPT_INPUT_NAMES
                and isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
            ):
                (negative if node_id in negatives else positive).add(value[0])
    linked = {
        node_id
        for node_id, node in graph.items()
        if any(isinstance(value, list) for value in node.get("inputs", {}).values())
    }
    return positive - linked, negative - positive - linked


def _field_id(node_id: str, name: str) -> str:
    return hashlib.sha256(json.dumps([node_id, name], separators=(",", ":")).encode()).hexdigest()


def _integer_as_string(spec: NodeInput, name: str, value: ScalarInput) -> bool:
    """整数是否可能超出 JavaScript 安全范围，需要以十进制字符串传给网页。

    当前值、字段上限或种子字段缺少安全上下限时为真。`value` 不是整数时抛出
    `TypeError` 或 `ValueError`。
    """
    if spec.kind != "integer":
        return False
    return (
        abs(int(value)) > MAX_SAFE_INTEGER
        or (spec.maximum is not None and Decimal(spec.maximum) > MAX_SAFE_INTEGER)
        or (
            _is_seed(spec.kind, name)
            and (
                spec.maximum is None
                or (spec.minimum is not None and Decimal(spec.minimum) < -MAX_SAFE_INTEGER)
            )
        )
    )


def _node_title(node: dict, definition: NodeCatalog) -> str:
    meta = node.get("_meta")
    return str((meta.get("title") if isinstance(meta, dict) else None) or definition.title)


def _reachable_graph(graph: dict, catalog: dict) -> dict:
    """从已知输出节点回溯依赖。未知节点可能是输出，保留全图供缺失节点校验。"""
    if any(node["class_type"] not in catalog for node in graph.values()):
        return graph
    pending = []
    for node_id, node in graph.items():
        spec = catalog[node["class_type"]]
        if spec.get("output_node"):
            pending.append(node_id)
    if not pending:
        return graph

    reachable = set()
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        for value in graph[node_id]["inputs"].values():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and value[0] in graph
                and type(value[1]) is int
            ):
                pending.append(value[0])
    if len(reachable) == len(graph):
        return graph
    return {node_id: node for node_id, node in graph.items() if node_id in reachable}


def _graph_fields(graph: dict, catalog: dict) -> tuple[list[WorkflowInput], list[str]]:
    """把图中可编辑的简单输入转成表单字段，同时收集缺少节点等问题。

    连接、复杂值和输出节点的输入保留在图内。字段默认值取自图，素材字段没有默认值。
    """
    fields: list[WorkflowInput] = []
    issues: list[str] = []
    negatives = _negative_prompt_nodes(graph)
    prompt_sources, negative_sources = _prompt_sources(graph, negatives)
    for node_id, node in graph.items():
        node_type = node["class_type"]
        raw = catalog.get(node_type)
        if raw is None:
            issues.append("缺少节点：" + node_type)
            continue
        definition = NodeCatalog.model_validate(raw)
        if definition.output_node:
            continue
        node_labels = {
            OUTPAINT_NODE: OUTPAINT_LABELS,
            "ImageCrop": {"x": "水平位置", "y": "垂直位置"},
            "ImageCompositeMasked": {"x": "水平位置", "y": "垂直位置"},
            "ImageRotate": {"rotation": "旋转角度"},
            MASK_NODE: {"image": "遮罩图片"},
        }.get(node_type, {})
        for name, value in node["inputs"].items():
            spec = definition.inputs.get(name)
            if not spec or isinstance(value, (list, dict)) or value is None:
                continue
            try:
                large_int = _integer_as_string(spec, name, value)
            except (TypeError, ValueError):
                issues.append("无效的数值默认值：" + name)
                continue
            media = spec.kind in MEDIA_INPUT_KINDS
            # 文本源节点上的文本字段按它接入的提示词输入归类。
            sourced = spec.kind == "string" and (
                spec.multiline
                or sum(
                    1
                    for other, raw_value in node["inputs"].items()
                    if isinstance(raw_value, str)
                    and (other_spec := definition.inputs.get(other))
                    and other_spec.kind == "string"
                )
                == 1
            )
            negative = (
                name == "negative_prompt"
                or (node_id in negatives and name in PROMPT_INPUT_NAMES)
                or (sourced and node_id in negative_sources)
            )
            prompt = spec.kind == "string" and (
                name in PROMPT_INPUT_NAMES or (sourced and node_id in prompt_sources)
            )
            known = (
                spec.label
                or node_labels.get(name)
                or LABELS.get(name)
                or ("提示词" if prompt else "")
            )
            fields.append(
                WorkflowInput(
                    **{
                        **spec.model_dump(),
                        "id": _field_id(node_id, name),
                        "node_id": node_id,
                        "input_name": name,
                        "node_title": _node_title(node, definition),
                        "default": None if media else str(value) if large_int else value,
                        "accepted_content_types": asset_content_types([spec.kind])
                        if media
                        else None,
                        "label": "负向提示词" if negative else known or name.replace("_", " "),
                        "named": negative or bool(known),
                        # 提示词与参考素材优先显示，其余进入高级参数。
                        "primary": media or (prompt and not negative),
                        "integer_as_string": large_int,
                    }
                )
            )
    return fields, issues


def _apply_author_defaults(
    fields: list[WorkflowInput], layout: list[WorkflowParameterDisplay], *, keep_original: bool
) -> dict[str, ScalarInput]:
    """用作者在参数布局里保存的默认值覆盖字段默认值。

    `keep_original` 为真时返回覆盖前的图默认值，供作者恢复。与当前工作机的类型、
    范围或步长不兼容的作者默认值被跳过，字段保留图默认值。
    """
    overrides = {entry.field_id: entry.default_value for entry in layout}
    original_defaults: dict[str, ScalarInput] = {}
    for field in fields:
        original = field.default
        if keep_original and original is not None and not isinstance(original, AssetReference):
            original_defaults[field.id] = (
                _float_default(field, original)
                if field.kind == "number" and type(original) is float
                else original
            )
        override = overrides.get(field.id)
        if override is not None:
            try:
                field.default = _encode_scalar(field, _scalar_value(field, override))
            except HTTPException:
                # 保留作者配置；不兼容的工作机使用原图默认值。
                continue
    return original_defaults


def _schema_hash(
    version: WorkflowVersion, graph: dict, fields: list[WorkflowInput], issues: list[str]
) -> str:
    """表单定义的指纹，绑定版本、执行节点和提交所需的有效字段。"""
    encoded = json.dumps(
        {
            "graph": version.graph_hash,
            "nodes": list(graph),
            "fields": [f.model_dump() for f in fields],
            "issues": issues,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def form_for(
    version: WorkflowVersion, machine: Machine, *, include_original_defaults: bool = False
) -> WorkflowForm:
    """根据 `version` 的节点和 `machine` 的输入定义生成表单与校验哈希。

    缺少节点写入表单的 `issues`。界面 JSON 返回 HTTP 422，节点目录尚未同步返回 409。
    图中的连接与复杂值保留在图内，只有已识别的简单输入会出现在表单。
    """
    matched(
        machine,
        version.worker_kind,
        version.connection_scope,
        machine.owner_id,
        team_id=machine.team_id,
    )
    if worker_type(version.worker_kind).form == "fields":
        data = official_form_for(version, include_original_defaults=include_original_defaults)
        return WorkflowForm(machine_id=machine.id, **data.model_dump())
    form, graph = _form_and_graph(
        version, machine, include_original_defaults=include_original_defaults
    )
    form.output_sizes = output_sizes_for(graph, form.fields)
    form.reference_timelines = reference_timelines_for(graph, form.fields)
    form.image_crops = image_crops_for(graph, form.fields)
    form.parameter_presentation = parameter_presentation_for(graph, form.fields)
    return form


def _form_and_graph(
    version: WorkflowVersion, machine: Machine, *, include_original_defaults: bool = False
) -> tuple[WorkflowForm, dict]:
    if version.format not in {"api", "remote"}:
        raise HTTPException(422, msg("input.exportTheApiVersionOfThe"))
    data = version.worker_data or {}
    catalog = data.get("catalog") if version.format == "remote" else machine.catalog
    if not catalog:
        raise HTTPException(409, msg("input.theWorkMachineHasNotSynced"))
    # An incomplete catalog can omit custom output-node markers.
    graph = version.graph if data.get("limited") else _reachable_graph(version.graph, catalog)
    fields, issues = _graph_fields(graph, catalog)
    if version.format == "api" and MASK_NODE in catalog:
        images = {
            field.node_id: field
            for field in fields
            if field.input_name == "image" and field.kind == "image"
        }
        for source, mask_node in native_mask_nodes(graph).items():
            if source not in images:
                continue
            fields.append(
                WorkflowInput(
                    id=_field_id(mask_node, "image"),
                    node_id=mask_node,
                    input_name="image",
                    node_title=images[source].node_title,
                    kind="image",
                    label="遮罩图片",
                    optional=True,
                    accepted_content_types=["image/png"],
                )
            )
    optional = {tuple(item) for item in data.get("optional_assets", [])}
    allowed = worker_type(version.worker_kind).input_kinds
    for field in fields:
        if (field.node_id, field.input_name) in optional:
            field.optional = True
        if field.kind not in allowed:
            issues.append("工作机不支持此输入类型：" + field.kind)
    layout = parameter_layout_for(version)
    original_defaults = _apply_author_defaults(
        fields, layout, keep_original=include_original_defaults
    )
    form = WorkflowForm(
        version_id=version.id,
        machine_id=machine.id,
        catalog_limited=bool(data.get("limited")),
        schema_hash=_schema_hash(version, graph, fields, issues),
        fields=fields,
        issues=issues,
        parameter_layout=layout,
        original_defaults=original_defaults,
    )
    return form, graph


def _localized_issue(issue: str, language: str) -> str:
    prefix, separator, argument = issue.partition("：")
    key = {"缺少节点": "input.missingNode", "无效的数值默认值": "input.invalidNumericDefault"}.get(
        prefix
    )
    return localize(msg(key, argument) if separator and key else issue, language)


def localize_form[T: WorkflowFormData](
    form: T, language: str, *, version: WorkflowVersion | None = None
) -> T:
    """Translate the response after computing the canonical execution schema hash."""
    if language != SOURCE_LANGUAGE:
        for field in form.fields:
            field.label = localize(field.label, language)
        form.issues = [_localized_issue(issue, language) for issue in form.issues]
        for presentation in form.parameter_presentation.values():
            presentation.choice_labels = {
                choice: localize(label, language)
                for choice, label in presentation.choice_labels.items()
            }
            if presentation.guidance:
                presentation.guidance = localize(presentation.guidance, language)
        for regions in form.image_crops.values():
            for region in regions:
                region.label = localize(region.label, language)
    if version is None or not version.translations:
        return form
    texts = version.translations.get(language) or version.translations.get(SOURCE_LANGUAGE, {})
    field_texts = texts.get("fields", {})
    for field in form.fields:
        text = field_texts.get(field.id, {})
        field.label = text.get("label") or field.label
        if labels := text.get("choice_labels"):
            presentation = form.parameter_presentation.setdefault(
                field.id, WorkflowParameterPresentation()
            )
            presentation.choice_labels = labels
    if version.parameter_layout is None:
        layout_texts = texts.get("parameter_layout", {})
        form.parameter_layout = [
            entry.model_copy(update=layout_texts.get(entry.field_id, {}))
            for entry in form.parameter_layout
        ]
    return form


def parameter_layout_for(version: WorkflowVersion) -> list[WorkflowParameterDisplay]:
    stored = version.parameter_layout
    if stored is None and worker_type(version.worker_kind).form == "fields":
        stored = version.graph.get("parameter_layout")
    return [WorkflowParameterDisplay.model_validate(entry) for entry in stored or []]


def _slider_for(field: WorkflowInput) -> ParameterSlider | None:
    if field.integer_as_string or field.minimum is None or field.maximum is None:
        return None
    minimum = Decimal(field.minimum)
    maximum = Decimal(field.maximum)
    step = Decimal(field.step or ("1" if field.kind == "integer" else "0"))
    with localcontext(prec=100, rounding=ROUND_FLOOR):
        if not -MAX_SAFE_INTEGER <= minimum < maximum <= MAX_SAFE_INTEGER:
            return None
        if not 0 < step <= maximum - minimum:
            return None
        # Radix moves in integer units so every position respects the decimal step.
        places = max(
            0,
            -int(minimum.normalize().as_tuple().exponent),
            -int(step.normalize().as_tuple().exponent),
        )
        if places > 15 or (field.kind == "integer" and places):
            return None
        scale = 10**places
        low = int(minimum * scale)
        high = int((maximum * scale).to_integral_value(rounding=ROUND_FLOOR))
        stride = int(step * scale)
        if minimum != Decimal(low) / scale or step != Decimal(stride) / scale:
            return None
    # Decimal values must also round-trip through JavaScript's number representation.
    limit = 10**15 - 1 if places else MAX_SAFE_INTEGER
    if not 0 < stride <= high - low <= limit or max(abs(low), abs(high)) > limit:
        return None
    return ParameterSlider(
        minimum=low, maximum=high - (high - low) % stride, step=stride, scale=scale
    )


def _controls_for(field: WorkflowInput) -> WorkflowParameterControls | None:
    if field.kind == "string":
        return WorkflowParameterControls(options=["text", "textarea"])
    if field.kind == "boolean":
        return WorkflowParameterControls(options=["checkbox"])
    if field.kind == "choice" and 2 <= len(field.choices) <= 8:
        return WorkflowParameterControls(options=["radio"])
    if field.kind in {"integer", "number"} and (slider := _slider_for(field)):
        return WorkflowParameterControls(options=["slider"], slider=slider)
    return None


def parameter_controls_for(fields: list[WorkflowInput]) -> dict[str, WorkflowParameterControls]:
    return {field.id: controls for field in fields if (controls := _controls_for(field))}


def validated_parameter_layout(
    fields: list[WorkflowInput],
    layout: list[WorkflowParameterDisplay],
    previous_layout: Sequence[WorkflowParameterDisplay] = (),
) -> list[WorkflowParameterDisplay]:
    """校验布局里的字段、控件和默认值，保留已存但当前目录未识别的字段。"""
    by_id = {field.id: field for field in fields}
    previous = {entry.field_id: entry for entry in previous_layout}
    seen = set()
    for entry in layout:
        field = by_id.get(entry.field_id)
        if field is None or entry.field_id in seen:
            raise HTTPException(422, msg("input.parametersChangedOrWereDuplicatedRefresh"))
        if entry.section == "hidden" and field.kind in MEDIA_INPUT_KINDS:
            raise HTTPException(
                422, msg("input.requiresAnUploadMoveItTo", message_from_text(field.label))
            )
        stored = previous.get(entry.field_id)
        if stored and "control" not in entry.model_fields_set:
            entry.control = stored.control
        # 换工作机时允许保留原有样式，新增或修改的样式必须与当前字段兼容。
        if entry.control is not None and (stored is None or entry.control != stored.control):
            controls = _controls_for(field)
            if controls is None or entry.control not in controls.options:
                raise HTTPException(
                    422,
                    msg("input.doesNotSupportTheSelectedControl", message_from_text(field.label)),
                )
        if stored and "default_value" not in entry.model_fields_set:
            entry.default_value = stored.default_value
        value = entry.default_value
        if value is not None and (
            stored is None
            or type(value) is not type(stored.default_value)
            or value != stored.default_value
        ):
            entry.default_value = _encode_scalar(field, _scalar_value(field, value))
        seen.add(entry.field_id)
    return layout + [entry for field_id, entry in previous.items() if field_id not in by_id]


def update_parameter_layout(
    version: WorkflowVersion, machine: Machine | None, layout: list[WorkflowParameterDisplay]
) -> list[WorkflowParameterDisplay]:
    definition = worker_type(version.worker_kind)
    if machine is not None:
        form = form_for(version, machine)
    elif definition.connection == "platform":
        form = official_form_for(version)
    else:
        raise HTTPException(422, msg("task.selectAnAvailableWorkMachine"))
    saved = validated_parameter_layout(form.fields, layout, form.parameter_layout)
    records = [entry.model_dump(exclude_none=True) for entry in saved]
    version.parameter_layout = records if definition.form == "fields" else records or None
    return saved


def _snap_float_noise(number: Decimal, origin: Decimal, step: Decimal, value: float) -> Decimal:
    """仅消除浮点运算尾差，保留刻度之间的合法值。"""
    try:
        remainder = (number - origin) % step
        if abs(remainder) > step / 2:
            remainder -= step.copy_sign(remainder)
        tolerance = min(4 * Decimal(str(math.ulp(value))), step / 1_000_000)
        return number - remainder if abs(remainder) <= tolerance else number
    except DecimalException:
        return number


def _check_number(
    field: WorkflowInput, number: Decimal, *, float_value: float | None = None
) -> Decimal:
    if not number.is_finite() or (field.kind == "integer" and number != number.to_integral_value()):
        raise ValueError()
    minimum = Decimal(field.minimum) if field.minimum is not None else None
    # 种子取范围内的任意整数，批量执行逐次加一，不受步长约束。
    if field.step is not None and (step := Decimal(field.step)) > 0:
        origin = minimum if minimum is not None else Decimal(0)
        if float_value is not None:
            number = _snap_float_noise(number, origin, step, float_value)
        elif (
            field.kind == "integer"
            and not _is_seed(field.kind, field.input_name)
            and (number - origin) % step
        ):
            raise ValueError()
    if minimum is not None and number < minimum:
        raise ValueError()
    if field.maximum is not None and number > Decimal(field.maximum):
        raise ValueError()
    return number


def _encode_integer(field: WorkflowInput, value: int) -> int | str:
    as_text = field.integer_as_string or (
        _is_seed(field.kind, field.input_name) and abs(value) > MAX_SAFE_INTEGER
    )
    return str(value) if as_text else value


def _numeric_value(field: WorkflowInput, value: InputValue) -> int | float:
    seed = _is_seed(field.kind, field.input_name)
    try:
        if field.kind == "integer":
            if field.integer_as_string or (seed and isinstance(value, str)):
                if not isinstance(value, str) or str(int(value)) != value:
                    raise ValueError()
            elif type(value) is not int:
                raise ValueError()
        elif type(value) not in {int, float}:
            raise ValueError()
        number = _check_number(
            field, Decimal(str(value)), float_value=value if type(value) is float else None
        )
        compiled = int(number) if field.kind == "integer" else float(number)
        if isinstance(compiled, float) and not math.isfinite(compiled):
            raise ValueError()
        return compiled
    except (DecimalException, ValueError, TypeError):
        reason = "input.invalidStep" if seed else "input.outOfRange"
        raise HTTPException(422, msg(reason, message_from_text(field.label))) from None


def _scalar_value(field: WorkflowInput, value: InputValue) -> ScalarInput:
    if field.kind in {"integer", "number"}:
        return _numeric_value(field, value)
    if field.kind == "boolean":
        if type(value) is not bool:
            raise HTTPException(422, msg("input.mustBeOnOrOff", message_from_text(field.label)))
        return value
    if field.kind == "choice":
        for choice in field.choices:
            if (
                type(value) is type(choice)
                or (type(value) in {int, float} and type(choice) in {int, float})
            ) and value == choice:
                return choice
        raise HTTPException(
            422,
            msg(
                "input.invalidChoiceForThisWorkMachine",
                message_from_text(field.label),
                str(value)[:120],
            ),
        )
    if field.kind in MEDIA_INPUT_KINDS:
        raise HTTPException(
            422, msg("input.provideAnAssetForWhenRunning", message_from_text(field.label))
        )
    if not isinstance(value, str):
        raise HTTPException(422, msg("input.onNodeMustBeText", field.node_id, field.input_name))
    limit = field.max_length or MAX_TEXT_INPUT_LENGTH
    if len(value) > limit:
        raise HTTPException(
            422,
            msg(
                "input.onNodeHasCharactersTheMaximum",
                field.node_id,
                field.input_name,
                len(value),
                limit,
            ),
        )
    return value


def _encode_scalar(field: WorkflowInput, value: ScalarInput) -> ScalarInput:
    if field.kind == "integer" and type(value) is int:
        return _encode_integer(field, value)
    return value


def official_input(
    definition: OfficialInput, declared_content_types: list[str] | None = None
) -> WorkflowInput:
    field = WorkflowInput(
        **definition.model_dump(exclude={"name", "choice_labels", "label"}),
        label=definition.label or definition.name,
        id=definition.name,
        node_id="inputs",
        input_name=definition.name,
        node_title="",
    )
    other_kinds = field.additional_asset_kinds or []
    if field.max_length is not None and field.kind != "string":
        raise HTTPException(422, msg("workflow.invalidData"))
    if definition.choice_labels and (
        field.kind != "choice"
        or definition.choice_labels.keys()
        - {value for value in field.choices if isinstance(value, str)}
    ):
        raise HTTPException(422, msg("workflow.invalidData"))
    if other_kinds and (
        field.kind not in MEDIA_INPUT_KINDS
        or field.kind in other_kinds
        or len(set(other_kinds)) != len(other_kinds)
    ):
        raise HTTPException(422, msg("workflow.invalidData"))
    if field.kind in MEDIA_INPUT_KINDS:
        if field.default is not None:
            raise HTTPException(422, msg("workflow.invalidData"))
        field.accepted_content_types = asset_content_types(
            [field.kind, *other_kinds], declared_content_types
        )
    elif field.default is not None or not field.optional:
        field.default = _encode_scalar(field, _scalar_value(field, field.default))
    return field


def official_form_for(
    version: WorkflowVersion, *, include_original_defaults: bool = False
) -> WorkflowFormData:
    if worker_type(version.worker_kind).form != "fields":
        raise HTTPException(404, msg("workflow.notFound"))
    definitions = [OfficialInput.model_validate(raw) for raw in version.graph["fields"]]
    content_types = atlas_asset_content_types(version.graph["execution"])
    fields = [
        official_input(definition, content_types.get(definition.name)) for definition in definitions
    ]
    layout = parameter_layout_for(version)
    original_defaults = _apply_author_defaults(
        fields, layout, keep_original=include_original_defaults
    )
    return WorkflowFormData(
        version_id=version.id,
        schema_hash=_schema_hash(version, version.graph["execution"], fields, []),
        fields=fields,
        parameter_layout=layout,
        parameter_presentation={
            definition.name: WorkflowParameterPresentation(choice_labels=definition.choice_labels)
            for definition in definitions
            if definition.choice_labels
        },
        original_defaults=original_defaults,
    )


def _float_default(field: WorkflowInput, value: float) -> float:
    try:
        return _numeric_value(field, value)
    except HTTPException:
        return value


def seed_fields(input_schema: dict) -> list[WorkflowInput]:
    return [
        WorkflowInput.model_validate(raw)
        for raw in input_schema["fields"]
        if _is_seed(raw["kind"], raw["input_name"])
    ]


def recorded_input(field: dict, language: str) -> RecordedInput:
    """读取提交时冻结的字段标识和展示信息。"""
    return RecordedInput(
        id=field["id"],
        label=localize(field["label"], language),
        node_id=field["node_id"],
        node_title=field["node_title"],
        input_name=field["input_name"],
    )


def _wire_integer(value: Decimal) -> int:
    limit = sys.get_int_max_str_digits()
    if limit and value and value.adjusted() >= limit:
        raise ValueError()
    return int(value)


def plan_execution_seeds(
    fields: list[WorkflowInput], values: dict, count: int
) -> list[dict[str, int | str]]:
    """从 `values` 的已选种子起，为 `count` 次执行依次加一。

    输出列表与执行序号对齐。超过字段上限后回到下限，大整数按字段定义编码。
    缺少种子或起始值超出字段范围时返回 HTTP 422。
    """
    planned: list[dict[str, int | str]] = [{} for _ in range(count)]
    for field in fields:
        try:
            stored = values[field.id]
            if type(stored) not in {int, str}:
                raise ValueError()
            start = int(stored)
            _check_number(field, Decimal(start))
            lower = (
                _wire_integer(Decimal(field.minimum).to_integral_value(rounding=ROUND_CEILING))
                if field.minimum is not None
                else min(0, start)
            )
            span = (
                _wire_integer(Decimal(field.maximum).to_integral_value(rounding=ROUND_FLOOR))
                - lower
                + 1
                if field.maximum is not None
                else None
            )
            for index, seeds in enumerate(planned):
                seed = start + index
                if span:
                    seed = lower + (seed - lower) % span
                seeds[field.id] = _encode_integer(field, seed)
        except (DecimalException, KeyError, ValueError, TypeError):
            raise HTTPException(
                422, msg("input.mustBeWithinTheWorkMachine", message_from_text(field.label))
            ) from None
    return planned


def compile_inputs(
    db: Session,
    version: WorkflowVersion,
    machine: Machine | None,
    values: dict,
    schema_hash: str | None,
    *,
    owner_id: str | None = None,
    team_id: str | None = None,
    language: str = SOURCE_LANGUAGE,
    work_assets: dict[str, WorkAsset] | None = None,
) -> tuple[dict, dict, dict, list[TaskAsset]]:
    """用 `schema_hash` 确认提交时的表单定义，再按字段 ID 校验 `values`。

    依次返回图的副本、标准化输入、表单快照和待写入的素材绑定。
    定义变更或依赖有问题返回 HTTP 409，素材不可访问返回 404，输入无效返回 422。
    """
    nodes = worker_type(version.worker_kind).form == "nodes"
    if machine:
        team_id = machine.team_id
        matched(
            machine,
            version.worker_kind,
            version.connection_scope,
            machine.owner_id,
            team_id=team_id,
        )
        owner_id = machine.owner_id
    if nodes and machine:
        form, execution_graph = _form_and_graph(version, machine)
    else:
        form, execution_graph = official_form_for(version), version.graph["execution"]
    if schema_hash is not None and form.schema_hash != schema_hash:
        message = (
            msg("workflow.theWorkflowChangedRefreshAndTry")
            if machine is None
            else msg("input.theWorkMachineSInputConfiguration")
        )
        raise HTTPException(409, message)
    if form.issues:
        separator = "；" if language == SOURCE_LANGUAGE else "\n"
        raise HTTPException(
            409, separator.join(_localized_issue(issue, language) for issue in form.issues)[:1000]
        )
    if not nodes:
        localize_form(form, language, version=version)
    by_id = {f.id: f for f in form.fields}
    if set(values) - by_id.keys():
        raise HTTPException(422, msg("input.thisParameterDoesNotBelongTo"))
    graph = deepcopy(execution_graph)
    image_crops = image_crops_for(graph, form.fields) if nodes else {}
    native_masks = (
        {mask: source for source, mask in native_mask_nodes(graph).items()} if nodes else {}
    )
    media_sizes: dict[str, tuple[int | None, int | None]] = {}
    normalized = {}
    assets = []
    for field in form.fields:
        value = values.get(field.id, field.default)
        if field.optional and (
            value is None
            or (machine is None and field.kind in {"number", "integer"} and value == "")
        ):
            continue
        if field.kind in MEDIA_INPUT_KINDS:
            if not isinstance(value, AssetReference):
                raise HTTPException(422, msg("input.upload", message_from_text(field.label)))
            if owner_id is None:
                raise HTTPException(404, msg("asset.notFound"))
            asset = (work_assets or {}).get(field.id) or owned_record(
                db, Asset, value.asset_id, owner_id, msg("asset.notFound"), team_id=team_id
            )
            if asset.content_type not in (field.accepted_content_types or []):
                raise HTTPException(
                    422, msg("input.theFileTypeForDoesNot", message_from_text(field.label))
                )
            if regions := image_crops.get(field.id):
                required_width = max(region.x + region.width for region in regions)
                required_height = max(region.y + region.height for region in regions)
                width, height = asset.media.width, asset.media.height
                if width is None or height is None:
                    raise HTTPException(
                        422,
                        msg(
                            "input.couldNotReadTheOriginalDimensions",
                            message_from_text(field.label),
                        ),
                    )
                if width < required_width or height < required_height:
                    raise HTTPException(
                        422,
                        msg(
                            "input.isPixelsTheCropExtendsPast",
                            message_from_text(field.label),
                            width,
                            height,
                            required_width,
                            required_height,
                        ),
                    )
            assets.append(
                TaskAsset(node_id=field.node_id, input_name=field.input_name, asset_id=asset.id)
            )
            normalized[field.id] = {"assetId": asset.id}
            if nodes:
                media_sizes[field.node_id] = (asset.media.width, asset.media.height)
                if field.node_id in native_masks:
                    source = native_masks[field.node_id]
                    if media_sizes.get(source) != media_sizes[field.node_id]:
                        raise HTTPException(422, msg("mask.dimensionsMustMatch"))
                    # Keep the source bytes intact, including RGB beneath transparent pixels.
                    for node in graph.values():
                        for key, link in node["inputs"].items():
                            if link == [source, 1]:
                                node["inputs"][key] = [field.node_id, 0]
                    graph[field.node_id] = {"class_type": MASK_NODE, "inputs": {"channel": "red"}}
                graph[field.node_id]["inputs"][field.input_name] = (
                    ASSET_PLACEHOLDER_PREFIX + asset.id
                )
            continue
        compiled = _scalar_value(field, value)
        if nodes:
            graph[field.node_id]["inputs"][field.input_name] = compiled
        normalized[field.id] = _encode_scalar(field, compiled)
    if nodes:
        validate_reference_timelines(graph, form.fields, normalized, form.parameter_layout)
    return (
        graph,
        normalized,
        form.model_dump(
            exclude={
                "parameter_layout",
                "parameter_controls",
                "parameter_presentation",
                "original_defaults",
                "shared_assets",
                "output_sizes",
                "reference_timelines",
                "image_crops",
                "cost_estimate",
            }
        ),
        assets,
    )


def replay_defaults[T: WorkflowFormData](form: T, values: dict) -> T:
    for field in form.fields:
        if field.id in values:
            value = values[field.id]
            if field.kind in MEDIA_INPUT_KINDS:
                # 同一个节点在不同工作机上可分别提供文件名选项和素材上传。
                if not isinstance(value, dict):
                    continue
                value = AssetReference.model_validate(value)
            elif isinstance(value, dict):
                # 目标工作机需要标量时，素材引用无法用作该字段的默认值。
                continue
            elif field.kind == "integer" and type(value) in {int, str}:
                try:
                    integer = int(value)
                except ValueError:
                    raise HTTPException(409, msg("input.theSavedInputDoesNotMatch")) from None
                value = _encode_integer(field, integer)
            field.default = value
    return form


def normalize_float_defaults[T: WorkflowFormData](form: T) -> T:
    """消除表单默认值的浮点尾差，保留需要用户修正的值。"""
    for field in form.fields:
        if field.kind == "number" and type(field.default) is float:
            field.default = _float_default(field, field.default)
    return form
