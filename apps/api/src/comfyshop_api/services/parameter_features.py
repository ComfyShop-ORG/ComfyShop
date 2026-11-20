"""识别图中支持组合交互的参数，只返回表单需要的字段引用。"""

import re

from fastapi import HTTPException

from comfyshop_api.schemas import (
    WorkflowAutomaticSize,
    WorkflowCropRegion,
    WorkflowInput,
    WorkflowParameterDisplay,
    WorkflowParameterPresentation,
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
                label = labels.get(frame.time_field_id) or f"第 {index} 张参考帧时间"
                raise HTTPException(
                    422,
                    f"{label}超出片段。片段有 {count} 帧，最后一帧约位于 {(count - 1) / fps:.2f} 秒。",
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


def parameter_presentation_for(
    graph: dict, fields: list[WorkflowInput]
) -> dict[str, WorkflowParameterPresentation]:
    guidance = _mesh_parameter_guidance(graph)
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
    return presentation
