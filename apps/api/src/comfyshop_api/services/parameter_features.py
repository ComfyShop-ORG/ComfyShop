"""识别图中支持组合交互的参数，只返回表单需要的字段引用。"""

import hashlib
import re

from fastapi import HTTPException

from comfyshop_api.core.i18n import msg
from comfyshop_api.schemas import (
    WorkflowAutomaticSize,
    WorkflowCropBox,
    WorkflowCropRegion,
    WorkflowInput,
    WorkflowMask,
    WorkflowOutpaint,
    WorkflowParameterDisplay,
    WorkflowParameterPresentation,
    WorkflowPlacementLayer,
    WorkflowRatioSize,
    WorkflowReferenceFrame,
    WorkflowReferenceTimeline,
)

_LATENT_MULTIPLES = {
    "EmptyLatentImage": 8,
    "EmptyFlux2LatentImage": 16,
    "MiniMaxH3ImageToVideo": 16,
    "MiniMaxH3ReferenceToVideo": 16,
    "MiniMaxH3ImageConditioning": 16,
    "PH3ImageConditioning": 16,
}
_H3_LENGTH_EXPRESSION = "max(5,round(a*24))+(5-(max(5,round(a*24))%17))%17"
_H3_FRAME_EXPRESSION = "round(a*24)"
_PIXAL_VIEWS = {"front": "正面", "left": "左侧", "back": "背面", "right": "右侧"}
OUTPAINT_NODE = "ImagePadForOutpaint"
OUTPAINT_LABELS = {"left": "左侧补画", "top": "上方补画", "right": "右侧补画", "bottom": "下方补画"}
MASK_NODE = "LoadImageMask"
INPAINT_NODES = {"InpaintModelConditioning", "VAEEncodeForInpaint", "SetLatentNoiseMask"}
_CHOICE_LABELS = {
    ("MoGeRender", "output"): {
        "depth": "深度图",
        "depth_colored": "彩色深度图",
        "normal_opengl": "法线图（OpenGL）",
        "normal_directx": "法线图（DirectX）",
        "mask": "遮罩",
    },
    ("ResolutionSelector", "aspect_ratio"): {
        "1:1 (Square)": "1:1 · 方形",
        "2:3 (Portrait Photo)": "2:3 · 竖版照片",
        "3:2 (Photo)": "3:2 · 横版照片",
        "3:4 (Portrait Standard)": "3:4 · 竖版",
        "4:3 (Standard)": "4:3 · 横版",
        "9:16 (Portrait Widescreen)": "9:16 · 竖屏",
        "16:9 (Widescreen)": "16:9 · 横屏",
        "21:9 (Ultrawide)": "21:9 · 超宽屏",
    },
}


def _linked_node(
    graph: dict, link: object, node_type: str, *, output: int = 0
) -> tuple[str, dict] | None:
    if (
        not isinstance(link, list)
        or len(link) != 2
        or not isinstance(link[0], str)
        or type(link[1]) is not int
        or link[1] != output
    ):
        return None
    node = graph.get(link[0])
    if node and node["class_type"] == node_type:
        return link[0], node["inputs"]
    return None


def qwen_prompt_preview(graph: dict) -> tuple[str, bool] | None:
    """找出原文和扩写共用一个输入的 Qwen 编码器及实际采用的分支。"""
    previews = set()
    for node in graph.values():
        if node["class_type"] != "TextEncodeQwenImage21":
            continue
        preview = _linked_node(graph, node["inputs"].get("prompt"), "PreviewAny")
        if not preview:
            return None
        switch = _linked_node(graph, preview[1].get("source"), "ComfySwitchNode")
        if not switch or type(switch[1].get("switch")) is not bool:
            return None
        original = switch[1].get("on_false")
        expanded = _linked_node(graph, switch[1].get("on_true"), "TextGenerate")
        if (
            not expanded
            or not _linked_node(graph, original, "PrimitiveStringMultiline")
            or expanded[1].get("prompt") != original
        ):
            return None
        previews.add((preview[0], switch[1]["switch"]))
    return next(iter(previews)) if len(previews) == 1 else None


def _size_axis(graph: dict, link: object, selector: str, output: int, fields: dict) -> int | None:
    rounded = 0
    math_node = _linked_node(graph, link, "ComfyMathExpression", output=1)
    if math_node:
        expression = fields.get((math_node[0], "expression"))
        if not expression or expression.default != "round(a/32)*32":
            return None
        rounded = 32
        link = math_node[1].get("values.a")
    passthrough = _linked_node(graph, link, "PrimitiveInt")
    if passthrough:
        link = passthrough[1].get("value")
    return rounded if link == [selector, output] else None


def _qwen21_sampler(graph: dict, latent_id: str) -> bool:
    for node in graph.values():
        inputs = node["inputs"]
        if inputs.get("latent_image") != [latent_id, 0]:
            continue
        if node["class_type"] == "KSampler":
            sampler = inputs
        elif node["class_type"] == "SamplerCustomAdvanced":
            guider = _linked_node(graph, inputs.get("guider"), "CFGGuider")
            if not guider:
                continue
            sampler = guider[1]
        else:
            continue
        if _linked_node(graph, sampler.get("model"), "QwenImage21Cache"):
            return True
    return False


def _size_alignment(
    graph: dict, selector: str, fields: dict
) -> tuple[int | None, int | None, int | None]:
    transforms = set()
    for node_id, node in graph.items():
        node_type = node["class_type"]
        multiple = _LATENT_MULTIPLES.get(node_type)
        if not multiple:
            continue
        inputs = node["inputs"]
        width = _size_axis(graph, inputs.get("width"), selector, 0, fields)
        height = _size_axis(graph, inputs.get("height"), selector, 1, fields)
        if width is not None and width == height:
            model_multiple = (
                16 if node_type == "EmptyLatentImage" and _qwen21_sampler(graph, node_id) else None
            )
            transforms.add((width or None, multiple, model_multiple))
    return transforms.pop() if len(transforms) == 1 else (None, None, None)


def _ph3_ratio_prompt(graph: dict, selector: str) -> str | None:
    """识别由同一个比例和提示词驱动的 P-H3 文生图，包含其扩写开关。"""
    for node in graph.values():
        if node["class_type"] != "PH3ImageConditioning":
            continue
        inputs = node["inputs"]
        if inputs.get("width") != [selector, 0] or inputs.get("height") != [selector, 1]:
            continue
        prompt = inputs.get("prompt")
        preview = _linked_node(graph, prompt, "PreviewAny")
        if preview:
            prompt = preview[1].get("source")
        switch = _linked_node(graph, prompt, "ComfySwitchNode")
        if switch:
            raw = switch[1].get("on_false")
            expanded = _linked_node(graph, switch[1].get("on_true"), "TextGenerateV2")
            if not expanded or expanded[1].get("prompt") != raw:
                continue
            prompt = raw
        source = _linked_node(graph, prompt, "PrimitiveStringMultiline")
        if source:
            text = source[1].get("value")
            if isinstance(text, str) and re.match(r"Aspect ratio: \d+:\d+[ \t]*\r?\n", text):
                return source[0]
    return None


def output_sizes_for(
    graph: dict, fields: list[WorkflowInput]
) -> list[WorkflowRatioSize | WorkflowAutomaticSize]:
    by_input = {(field.node_id, field.input_name): field for field in fields}
    sizes: list[WorkflowRatioSize | WorkflowAutomaticSize] = []
    for node_id, node in graph.items():
        if node["class_type"] == "ResolutionSelector":
            aspect = by_input.get((node_id, "aspect_ratio"))
            pixels = by_input.get((node_id, "megapixels"))
            step = by_input.get((node_id, "multiple"))
            if not aspect or aspect.kind != "choice" or not pixels or not step:
                continue
            if pixels.kind != "number" or step.kind != "integer" or step.integer_as_string:
                continue
            round_to, latent_multiple, model_multiple = _size_alignment(graph, node_id, by_input)
            prompt_node = _ph3_ratio_prompt(graph, node_id)
            prompt = by_input.get((prompt_node, "value")) if prompt_node else None
            sizes.append(
                WorkflowRatioSize(
                    ratio_field_id=aspect.id,
                    megapixels_field_id=pixels.id,
                    multiple_field_id=step.id,
                    round_to=round_to,
                    latent_multiple=latent_multiple,
                    model_multiple=model_multiple,
                    prompt_field_id=prompt.id if prompt and prompt.kind == "string" else None,
                )
            )
        elif node["class_type"] == "TextEncodeFibo2":
            width = by_input.get((node_id, "width"))
            height = by_input.get((node_id, "height"))
            if (
                not width
                or not height
                or any(side.kind != "integer" or side.integer_as_string for side in (width, height))
            ):
                continue
            sizes.append(
                WorkflowAutomaticSize(
                    width_field_id=width.id,
                    height_field_id=height.id,
                    uses_reference=any(
                        name.startswith("images.") and isinstance(value, list)
                        for name, value in node["inputs"].items()
                    ),
                )
            )
    return sizes


def _image_field(graph: dict, fields: dict, link: object) -> WorkflowInput | None:
    image = _linked_node(graph, link, "LoadImage")
    field = fields.get((image[0], "image")) if image else None
    return field if field and field.kind == "image" else None


def _seconds_field(
    graph: dict, fields: dict, link: object, formula: str, compiled: bool
) -> WorkflowInput | None:
    math = _linked_node(graph, link, "ComfyMathExpression", output=1)
    if not math:
        return None
    expression = fields.get((math[0], "expression"))
    effective = expression.default if expression and not compiled else math[1].get("expression")
    if not isinstance(effective, str) or "".join(effective.split()) != formula:
        return None
    seconds = _linked_node(graph, math[1].get("values.a"), "PrimitiveFloat")
    field = fields.get((seconds[0], "value")) if seconds else None
    return field if field and field.kind == "number" else None


def reference_timelines_for(
    graph: dict, fields: list[WorkflowInput], *, compiled: bool = False
) -> list[WorkflowReferenceTimeline]:
    by_input = {(field.node_id, field.input_name): field for field in fields}
    guides = {
        node_id: node["inputs"]
        for node_id, node in graph.items()
        if node["class_type"] == "MiniMaxH3AddGuide"
    }
    timelines = []
    for node_id, node in graph.items():
        if node["class_type"] != "MiniMaxH3ReferenceToVideo":
            continue
        inputs = node["inputs"]
        duration = _seconds_field(
            graph, by_input, inputs.get("length"), _H3_LENGTH_EXPRESSION, compiled
        )
        first = _image_field(graph, by_input, inputs.get("ref_images.ref_image_0"))
        if not duration or not first:
            continue
        frames = [WorkflowReferenceFrame(image_field_id=first.id)]
        parent = node_id
        seen = {parent}
        while True:
            downstream = [
                (guide_id, guide)
                for guide_id, guide in guides.items()
                if guide.get("positive") == [parent, 0] and guide.get("latent") == [node_id, 1]
            ]
            if not downstream:
                break
            guide_id, guide = downstream[0]
            image = _image_field(graph, by_input, guide.get("image"))
            time = _seconds_field(
                graph, by_input, guide.get("frame_idx"), _H3_FRAME_EXPRESSION, compiled
            )
            if (
                len(downstream) != 1
                or guide_id in seen
                or not image
                or not time
                or guide.get("audio")
            ):
                frames = []
                break
            frames.append(WorkflowReferenceFrame(image_field_id=image.id, time_field_id=time.id))
            parent = guide_id
            seen.add(guide_id)
        if len(frames) > 1:
            timelines.append(
                WorkflowReferenceTimeline(duration_field_id=duration.id, frames=frames)
            )
    return timelines


def validate_reference_timelines(
    graph: dict, fields: list[WorkflowInput], values: dict, layout: list[WorkflowParameterDisplay]
) -> None:
    timelines = reference_timelines_for(graph, fields, compiled=True)
    if not timelines:
        return
    labels = {row.field_id: row.display_name for row in layout if row.display_name}
    for timeline in timelines:
        fps = timeline.frames_per_second
        minimum = timeline.minimum_frames
        count = max(minimum, round(values[timeline.duration_field_id] * fps))
        count += (minimum - count) % timeline.frame_step
        for index, frame in enumerate(timeline.frames[1:], start=2):
            if frame.time_field_id is None:
                continue
            position = round(values[frame.time_field_id] * fps)
            # 和 ComfyUI 一致，负帧号从片段末尾计数。
            if not -count <= position < count:
                label = labels.get(frame.time_field_id) or msg(
                    "input.referenceFrameTimestamp", index
                )
                raise HTTPException(
                    422,
                    msg(
                        "media.fallsOutsideTheClipTheClip",
                        label,
                        count,
                        f"{(count - 1) / fps:.2f}",
                    ),
                )


def _view_crop(
    graph: dict, fields: dict, link: object, label: str
) -> tuple[str, WorkflowCropRegion] | None:
    saved = _linked_node(graph, link, "SaveImageAdvanced")
    if saved:
        link = saved[1].get("images")
    cropped_to_mask = _linked_node(graph, link, "ImageCropToMask")
    if cropped_to_mask:
        link = cropped_to_mask[1].get("images")
    crop = _linked_node(graph, link, "ImageCropV2")
    if not crop:
        return None
    image = _image_field(graph, fields, crop[1].get("image"))
    bounds = crop[1].get("crop_region")
    if not image or not isinstance(bounds, dict):
        return None
    x, y, width, height = (bounds.get(key) for key in ("x", "y", "width", "height"))
    if (
        type(x) is not int
        or type(y) is not int
        or type(width) is not int
        or type(height) is not int
    ):
        return None
    if min(x, y) < 0 or min(width, height) <= 0 or max(x, y, width, height) >= 2**31:
        return None
    return image.id, WorkflowCropRegion(label=label, x=x, y=y, width=width, height=height)


def image_crops_for(
    graph: dict, fields: list[WorkflowInput]
) -> dict[str, list[WorkflowCropRegion]]:
    by_input = {(field.node_id, field.input_name): field for field in fields}
    crops = {}
    for node in graph.values():
        if node["class_type"] != "Pixal3DMultiViewConditioning":
            continue
        matches = []
        for role, label in _PIXAL_VIEWS.items():
            view = _view_crop(graph, by_input, node["inputs"].get(role), label)
            if view:
                matches.append(view)
        if len(matches) != len(_PIXAL_VIEWS):
            continue
        field_id = matches[0][0]
        if all(image_id == field_id for image_id, _ in matches):
            crops[field_id] = sorted(
                (region for _, region in matches), key=lambda region: (region.x, region.y)
            )
    return crops


def _choice_labels(node_type: str, field: WorkflowInput) -> dict[str, str]:
    labels = _CHOICE_LABELS.get((node_type, field.input_name), {})
    return {
        choice: labels[choice]
        for choice in field.choices
        if isinstance(choice, str) and choice in labels
    }


def _mesh_parameter_guidance(graph: dict) -> dict[tuple[str, str], str]:
    notes = {}
    for node_id, node in graph.items():
        if node["class_type"] == "BakeTextureFromVoxel":
            linked = _linked_node(graph, node["inputs"].get("texture_size"), "PrimitiveInt")
            field = (linked[0], "value") if linked else (node_id, "texture_size")
            notes[field] = (
                "材质贴图按像素设置宽高。提高分辨率能保留更多材质细节，也会增加显存和成品体积。"
            )
        elif node["class_type"] == "DecimateMesh":
            linked = _linked_node(graph, node["inputs"].get("target_face_count"), "PrimitiveInt")
            field = (linked[0], "value") if linked else (node_id, "target_face_count")
            notes[field] = "面数控制网格复杂度。减少面数可减小模型体积，细小轮廓也可能被简化。"
    return notes


def _inpaint_connections(graph: dict, node: dict) -> tuple[object, object]:
    inputs = node["inputs"]
    pixels = inputs.get("pixels")
    if node["class_type"] == "SetLatentNoiseMask":
        encoder = _linked_node(graph, inputs.get("samples"), "VAEEncode")
        pixels = encoder[1].get("pixels") if encoder else None
    mask = inputs.get("mask")
    # Grow and feather operate on the source mask without changing its polarity.
    seen: set[str] = set()
    while step := (
        _linked_node(graph, mask, "GrowMask") or _linked_node(graph, mask, "FeatherMask")
    ):
        if step[0] in seen:
            return pixels, None
        seen.add(step[0])
        mask = step[1].get("mask")
    return pixels, mask


def native_mask_nodes(graph: dict) -> dict[str, str]:
    """Return a stable optional mask-node ID for each unambiguous LoadImage pair."""
    uses: dict[str, list] = {}
    mask_users: dict[str, set[str | None]] = {}
    for node in graph.values():
        if node["class_type"] not in INPAINT_NODES:
            continue
        pixels, mask_link = _inpaint_connections(graph, node)
        image = _linked_node(graph, pixels, "LoadImage")
        mask = _linked_node(graph, mask_link, "LoadImage", output=1)
        if image:
            uses.setdefault(image[0], []).append(mask_link)
        if mask:
            mask_users.setdefault(mask[0], set()).add(image[0] if image else None)
    nodes = {}
    for source, links in uses.items():
        if mask_users.get(source) != {source} or any(link != [source, 1] for link in links):
            continue
        base = "comfyshop_mask_" + hashlib.sha256(source.encode()).hexdigest()
        candidate = base
        suffix = 0
        while candidate in graph:
            suffix += 1
            candidate = f"{base}_{suffix}"
        nodes[source] = candidate
    return nodes


def _mask_inputs(
    graph: dict, fields: dict[tuple[str, str], WorkflowInput]
) -> dict[str, WorkflowMask]:
    by_image: dict[str, dict[str | None, WorkflowMask | None]] = {}
    sources_by_mask: dict[str, set[str]] = {}
    for node in graph.values():
        if node["class_type"] not in INPAINT_NODES:
            continue
        pixels, mask_link = _inpaint_connections(graph, node)
        image = _image_field(graph, fields, pixels)
        linked = _linked_node(graph, mask_link, MASK_NODE)
        if not image:
            continue
        if not linked:
            by_image.setdefault(image.id, {})[None] = None
            continue
        mask = fields.get((linked[0], "image"))
        channel = fields.get((linked[0], "channel"))
        if not mask or mask.kind != "image":
            continue
        masks = by_image.setdefault(image.id, {})
        sources_by_mask.setdefault(mask.id, set()).add(image.id)
        masks[mask.id] = (
            WorkflowMask(field_id=mask.id, channel_field_id=channel.id)
            if channel and channel.kind == "choice" and channel.default == "red"
            else None
        )
    bindings = {
        image_id: binding
        for image_id, masks in by_image.items()
        if len(masks) == 1
        for mask_id, binding in masks.items()
        if binding is not None and mask_id is not None and len(sources_by_mask[mask_id]) == 1
    }
    for source, node_id in native_mask_nodes(graph).items():
        image = fields.get((source, "image"))
        override = fields.get((node_id, "image"))
        if image and override:
            bindings[image.id] = WorkflowMask(field_id=override.id)
    return bindings


def _placement_layer(
    graph: dict, fields: dict[tuple[str, str], WorkflowInput], node_id: str, inputs: dict
) -> WorkflowPlacementLayer | None:
    source = inputs.get("source")
    mask = inputs.get("mask")
    opacity = _linked_node(graph, mask, "InvertMask")
    split = _linked_node(graph, source, "SplitImageWithAlpha")
    if split:
        if not opacity or opacity[1].get("mask") != [split[0], 1]:
            return None
        source = split[1].get("image")
    rotation = _linked_node(graph, source, "ImageRotate")
    if rotation:
        source = rotation[1].get("image")
    scale = _linked_node(graph, source, "ImageScaleBy")
    if scale:
        source = scale[1].get("image")
    if split:
        joined = _linked_node(graph, source, "JoinImageWithAlpha")
        if not joined:
            return None
        source = joined[1].get("image")
    else:
        joined = None
    image = _image_field(graph, fields, source)
    if not image:
        return None
    alpha = [image.node_id, 1]
    if joined:
        if joined[1].get("alpha") != alpha:
            return None
    elif mask is not None and (not opacity or opacity[1].get("mask") != alpha or rotation):
        return None

    x = fields.get((node_id, "x"))
    y = fields.get((node_id, "y"))
    resize = fields.get((node_id, "resize_source"))
    factor = fields.get((scale[0], "scale_by")) if scale else None
    angle = fields.get((rotation[0], "rotation")) if rotation else None
    if (
        not x
        or not y
        or any(f.kind != "integer" or f.integer_as_string for f in (x, y))
        or not resize
        or resize.kind != "boolean"
        or (scale and (not factor or factor.kind != "number"))
        or (rotation and (not angle or angle.kind != "choice"))
    ):
        return None
    return WorkflowPlacementLayer(
        image=image.id,
        x=x.id,
        y=y.id,
        resize=resize.id,
        scale=factor.id if factor else None,
        rotation=angle.id if angle else None,
        alpha=mask is not None,
    )


def _placement_inputs(
    graph: dict, fields: dict[tuple[str, str], WorkflowInput]
) -> dict[str, list[WorkflowPlacementLayer]]:
    children: dict[str, list[str]] = {}
    for node_id, node in graph.items():
        link = node["inputs"].get("destination")
        if (
            node["class_type"] == "ImageCompositeMasked"
            and isinstance(link, list)
            and len(link) == 2
            and isinstance(link[0], str)
            and type(link[1]) is int
            and link[1] == 0
        ):
            children.setdefault(link[0], []).append(node_id)
    placements = {}
    for root in children:
        background = _image_field(graph, fields, [root, 0])
        if not background:
            continue
        layers = []
        used = set()
        parent = root
        while downstream := children.get(parent):
            if len(downstream) != 1:
                break
            parent = downstream[0]
            layer = _placement_layer(graph, fields, parent, graph[parent]["inputs"])
            if not layer:
                break
            controls = {key for key in (layer.x, layer.y, layer.scale, layer.rotation) if key}
            if used & controls:
                break
            used |= controls
            layers.append(layer)
        else:
            if layers:
                placements[background.id] = layers
    return placements


def parameter_presentation_for(
    graph: dict, fields: list[WorkflowInput]
) -> dict[str, WorkflowParameterPresentation]:
    guidance = _mesh_parameter_guidance(graph)
    by_input = {(field.node_id, field.input_name): field for field in fields}
    presentation = {}
    for field in fields:
        if field.kind == "choice":
            labels = _choice_labels(graph[field.node_id]["class_type"], field)
            if labels:
                presentation[field.id] = WorkflowParameterPresentation(choice_labels=labels)
        elif field.kind == "integer":
            note = guidance.get((field.node_id, field.input_name))
            if note:
                presentation[field.id] = WorkflowParameterPresentation(guidance=note)
    for node_type, names in (
        (OUTPAINT_NODE, tuple(OUTPAINT_LABELS)),
        ("ImageCrop", ("x", "y", "width", "height")),
    ):
        nodes_by_image: dict[str, str | None] = {}
        for node_id, node in graph.items():
            if node["class_type"] == node_type and (
                image := _image_field(graph, by_input, node["inputs"].get("image"))
            ):
                nodes_by_image[image.id] = None if image.id in nodes_by_image else node_id
        for image_id, node_id in nodes_by_image.items():
            if node_id is None:
                continue
            mapping = {
                name: field.id
                for name in names
                if (field := by_input.get((node_id, name)))
                and field.kind == "integer"
                and not field.integer_as_string
            }
            if len(mapping) == len(names):
                entry = presentation.setdefault(image_id, WorkflowParameterPresentation())
                if node_type == OUTPAINT_NODE:
                    entry.outpaint = WorkflowOutpaint(**mapping)
                else:
                    entry.crop = WorkflowCropBox(**mapping)
    for image_id, layers in _placement_inputs(graph, by_input).items():
        presentation.setdefault(image_id, WorkflowParameterPresentation()).layers = layers
    for image_id, mask in _mask_inputs(graph, by_input).items():
        presentation.setdefault(image_id, WorkflowParameterPresentation()).mask = mask
    return presentation
