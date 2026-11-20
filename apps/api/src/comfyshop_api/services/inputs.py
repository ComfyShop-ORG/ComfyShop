"""把工作流版本与工作机目录编成网页表单，再将用户输入冻结为可执行的任务快照。"""

from copy import deepcopy
from decimal import Decimal, DecimalException, ROUND_CEILING, ROUND_FLOOR, localcontext
import hashlib
import json
import math
import sys

from fastapi import HTTPException
from sqlalchemy.orm import Session

from comfyshop_api.models import Asset, Machine, TaskAsset, WorkflowVersion
from comfyshop_api.services.media_records import media_kind
from comfyshop_api.services.parameter_features import (
    image_crops_for,
    output_sizes_for,
    parameter_presentation_for,
    reference_timelines_for,
    validate_reference_timelines,
)
from comfyshop_api.schemas import (
    AssetReference,
    InputValue,
    MEDIA_INPUT_KINDS,
    NodeCatalog,
    NodeInput,
    ParameterSlider,
    ScalarInput,
    WorkflowForm,
    WorkflowInput,
    WorkflowParameterControls,
    WorkflowParameterDisplay,
)

MAX_SAFE_INTEGER = 2**53 - 1
MAX_TEXT_INPUT_LENGTH = 65_536
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
    """保守地从已知输出节点回溯依赖。目录不完整时，由 ComfyUI 确认执行范围。"""
    if any(node["class_type"] not in catalog for node in graph.values()):
        return graph
    pending = []
    for node_id, node in graph.items():
        spec = catalog[node["class_type"]]
        if spec.get("output_node", spec.get("outputNode", False)):
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
        raw = catalog.get(node["class_type"])
        if raw is None:
            issues.append("缺少节点：" + node["class_type"])
            continue
        definition = NodeCatalog.model_validate(raw)
        if definition.output_node:
            continue
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
            known = spec.label or LABELS.get(name) or ("提示词" if prompt else "")
            fields.append(
                WorkflowInput(
                    **{
                        **spec.model_dump(),
                        "id": _field_id(node_id, name),
                        "node_id": node_id,
                        "input_name": name,
                        "node_title": _node_title(node, definition),
                        "default": None if media else str(value) if large_int else value,
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
    if version.format != "api":
        raise HTTPException(422, "请从 ComfyUI 导出 API 格式的工作流")
    if not machine.catalog:
        raise HTTPException(409, "工作机尚未同步节点定义")
    graph = _reachable_graph(version.graph, machine.catalog)
    fields, issues = _graph_fields(graph, machine.catalog)
    layout = parameter_layout_for(version)
    original_defaults = _apply_author_defaults(
        fields, layout, keep_original=include_original_defaults
    )
    form = WorkflowForm(
        version_id=version.id,
        machine_id=machine.id,
        schema_hash=_schema_hash(version, graph, fields, issues),
        fields=fields,
        issues=issues,
        parameter_layout=layout,
        original_defaults=original_defaults,
    )
    return form, graph


def parameter_layout_for(version: WorkflowVersion) -> list[WorkflowParameterDisplay]:
    return [
        WorkflowParameterDisplay.model_validate(entry) for entry in version.parameter_layout or []
    ]


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


def update_parameter_layout(
    version: WorkflowVersion, machine: Machine, layout: list[WorkflowParameterDisplay]
) -> list[WorkflowParameterDisplay]:
    """校验所选工作机的表单字段，保留该工作机未识别的既有展示配置。"""
    form = form_for(version, machine)
    fields = {field.id: field for field in form.fields}
    previous = {entry.field_id: entry for entry in form.parameter_layout}
    seen = set()
    for entry in layout:
        field = fields.get(entry.field_id)
        if field is None or entry.field_id in seen:
            raise HTTPException(422, "参数有重复或已变化，请刷新后重试")
        if entry.section == "hidden" and field.kind in MEDIA_INPUT_KINDS:
            raise HTTPException(422, f"{field.label}需要上传，请放到可见区域")
        stored = previous.get(entry.field_id)
        if stored and "control" not in entry.model_fields_set:
            entry.control = stored.control
        # 换工作机时允许保留原有样式，新增或修改的样式必须与当前字段兼容。
        if entry.control is not None and (stored is None or entry.control != stored.control):
            controls = _controls_for(field)
            if controls is None or entry.control not in controls.options:
                raise HTTPException(422, f"{field.label}不支持所选显示方式")
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
    saved = layout + [entry for field_id, entry in previous.items() if field_id not in fields]
    version.parameter_layout = [entry.model_dump(exclude_none=True) for entry in saved] or None
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
        reason = "需符合工作机的范围与步长" if seed else "超出允许范围"
        raise HTTPException(422, field.label + reason) from None


def _scalar_value(field: WorkflowInput, value: InputValue) -> ScalarInput:
    if field.kind in {"integer", "number"}:
        return _numeric_value(field, value)
    if field.kind == "boolean":
        if type(value) is not bool:
            raise HTTPException(422, f"{field.label}必须为开关值")
        return value
    if field.kind == "choice":
        for choice in field.choices:
            if (
                type(value) is type(choice)
                or (type(value) in {int, float} and type(choice) in {int, float})
            ) and value == choice:
                return choice
        raise HTTPException(422, f"{field.label}的选项无效：当前工作机没有「{str(value)[:120]}」")
    if field.kind in MEDIA_INPUT_KINDS:
        raise HTTPException(422, f"{field.label}需要在运行时提供素材")
    if not isinstance(value, str):
        raise HTTPException(422, f"节点 {field.node_id} 的「{field.input_name}」必须是文本")
    if len(value) > MAX_TEXT_INPUT_LENGTH:
        raise HTTPException(
            422,
            f"节点 {field.node_id} 的「{field.input_name}」有 {len(value)} 个字符，"
            f"最多允许 {MAX_TEXT_INPUT_LENGTH} 个字符",
        )
    return value


def _encode_scalar(field: WorkflowInput, value: ScalarInput) -> ScalarInput:
    if field.kind == "integer" and type(value) is int:
        return _encode_integer(field, value)
    return value


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
            raise HTTPException(422, f"{field.label}需在工作机允许的范围内") from None
    return planned


def compile_inputs(
    db: Session, version: WorkflowVersion, machine: Machine, values: dict, schema_hash: str
) -> tuple[dict, dict, dict, list[TaskAsset]]:
    """用 `schema_hash` 确认提交时的表单定义，再按字段 ID 校验 `values`。

    依次返回图的副本、标准化输入、表单快照和待写入的素材绑定。
    定义变更或依赖有问题返回 HTTP 409，素材不可访问返回 404，输入无效返回 422。
    """
    form, execution_graph = _form_and_graph(version, machine)
    if form.schema_hash != schema_hash:
        raise HTTPException(409, "工作机输入配置已更新，请刷新后重试")
    if form.issues:
        raise HTTPException(409, "；".join(form.issues)[:1000])
    by_id = {f.id: f for f in form.fields}
    if set(values) - by_id.keys():
        raise HTTPException(422, "参数不属于当前工作流")
    graph = deepcopy(execution_graph)
    normalized = {}
    assets = []
    for field in form.fields:
        value = values.get(field.id, field.default)
        if field.kind in MEDIA_INPUT_KINDS:
            if not isinstance(value, AssetReference):
                raise HTTPException(422, f"请上传{field.label}")
            asset = db.get(Asset, value.asset_id)
            if not asset or asset.owner_id != machine.owner_id:
                raise HTTPException(404, "素材不存在")
            if media_kind(asset.media.content_type) != field.kind:
                raise HTTPException(422, f"{field.label}的文件类型不匹配")
            assets.append(
                TaskAsset(node_id=field.node_id, input_name=field.input_name, asset_id=asset.id)
            )
            normalized[field.id] = {"assetId": asset.id}
            graph[field.node_id]["inputs"][field.input_name] = "__comfyshop_asset__:" + asset.id
            continue
        compiled = _scalar_value(field, value)
        graph[field.node_id]["inputs"][field.input_name] = compiled
        normalized[field.id] = _encode_scalar(field, compiled)
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
            }
        ),
        assets,
    )


def replay_defaults(form: WorkflowForm, values: dict) -> WorkflowForm:
    for field in form.fields:
        if field.id in values:
            value = values[field.id]
            if field.kind in MEDIA_INPUT_KINDS:
                # 旧目录可能把工作机文件名保存成普通选项。
                if not isinstance(value, dict):
                    continue
                value = AssetReference.model_validate(value)
            elif isinstance(value, dict):
                # 当前工作机将旧素材字段定义为普通参数时，使用当前字段默认值。
                continue
            elif field.kind == "integer" and type(value) in {int, str}:
                try:
                    integer = int(value)
                except ValueError:
                    raise HTTPException(409, "历史输入不符合当前工作机的整数定义") from None
                value = _encode_integer(field, integer)
            field.default = value
    return form


def normalize_float_defaults(form: WorkflowForm) -> WorkflowForm:
    """消除表单默认值的浮点尾差，保留需要用户修正的值。"""
    for field in form.fields:
        if field.kind == "number" and type(field.default) is float:
            field.default = _float_default(field, field.default)
    return form
