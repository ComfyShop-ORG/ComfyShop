import pytest
from fastapi import HTTPException

from comfyshop_api.schemas import WorkflowInput, WorkflowParameterDisplay
from comfyshop_api.services.parameter_features import (
    image_crops_for,
    output_sizes_for,
    parameter_presentation_for,
    reference_timelines_for,
    validate_reference_timelines,
)


def _field(node_id, name, kind):
    return WorkflowInput(
        id=f"{node_id}.{name}", node_id=node_id, input_name=name, node_title=node_id, kind=kind
    )


def test_resolution_uses_the_connected_ph3_prompt_only():
    graph = {
        "size": {"class_type": "ResolutionSelector", "inputs": {}},
        "prompt": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": "Aspect ratio: 4:3\nRequest: landscape"},
        },
        "expanded": {"class_type": "TextGenerateV2", "inputs": {"prompt": ["prompt", 0]}},
        "switch": {
            "class_type": "ComfySwitchNode",
            "inputs": {"on_true": ["expanded", 0], "on_false": ["prompt", 0]},
        },
        "preview": {"class_type": "PreviewAny", "inputs": {"source": ["switch", 0]}},
        "condition": {
            "class_type": "PH3ImageConditioning",
            "inputs": {"width": ["size", 0], "height": ["size", 1], "prompt": ["preview", 0]},
        },
    }
    fields = [
        _field("size", "aspect_ratio", "choice"),
        _field("size", "megapixels", "number"),
        _field("size", "multiple", "integer"),
        _field("prompt", "value", "string"),
    ]
    size = output_sizes_for(graph, fields)[0]
    assert size.kind == "ratio"
    assert size.model_dump() == {
        "kind": "ratio",
        "ratio_field_id": "size.aspect_ratio",
        "megapixels_field_id": "size.megapixels",
        "multiple_field_id": "size.multiple",
        "round_to": None,
        "latent_multiple": 16,
        "model_multiple": None,
        "prompt_field_id": "prompt.value",
    }
    graph["expanded"]["inputs"]["prompt"] = ["another_prompt", 0]
    unlinked = output_sizes_for(graph, fields)[0]
    assert unlinked.kind == "ratio" and unlinked.prompt_field_id is None
    assert not output_sizes_for(graph, fields[:2])


def test_h3_timing_follows_guide_connections_and_checks_aligned_length():
    graph = {
        "first": {"class_type": "LoadImage", "inputs": {"image": "first.png"}},
        "second": {"class_type": "LoadImage", "inputs": {"image": "second.png"}},
        "duration": {"class_type": "PrimitiveFloat", "inputs": {"value": 5}},
        "time": {"class_type": "PrimitiveFloat", "inputs": {"value": 5}},
        "length": {
            "class_type": "ComfyMathExpression",
            "inputs": {
                "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
                "values.a": ["duration", 0],
            },
        },
        "frame": {
            "class_type": "ComfyMathExpression",
            "inputs": {"expression": "round (a * 24)", "values.a": ["time", 0]},
        },
        "base": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {"ref_images.ref_image_0": ["first", 0], "length": ["length", 1]},
        },
        "guide": {
            "class_type": "MiniMaxH3AddGuide",
            "inputs": {
                "image": ["second", 0],
                "positive": ["base", 0],
                "latent": ["base", 1],
                "frame_idx": ["frame", 1],
            },
        },
    }
    fields = [
        _field("first", "image", "image"),
        _field("second", "image", "image"),
        _field("duration", "value", "number"),
        _field("time", "value", "number"),
    ]
    timeline = reference_timelines_for(graph, fields)[0]
    assert timeline.duration_field_id == "duration.value"
    assert [(frame.image_field_id, frame.time_field_id) for frame in timeline.frames] == [
        ("first.image", None),
        ("second.image", "time.value"),
    ]
    label = WorkflowParameterDisplay(
        field_id="f" * 64, section="advanced", display_name="参考图时间"
    )
    fields[-1].id = label.field_id
    values = {"duration.value": 4.9, label.field_id: 5}
    validate_reference_timelines(graph, fields, values, [label])
    values["duration.value"] = 4.4
    with pytest.raises(HTTPException) as error:
        validate_reference_timelines(graph, fields, values, [label])
    assert error.value.status_code == 422
    detail = str(error.value.detail)
    assert "参考图时间" in detail and "107 帧" in detail
    values[label.field_id] = -1
    validate_reference_timelines(graph, fields, values, [label])
    graph["frame"]["inputs"]["expression"] = "round (a * 12)"
    assert not reference_timelines_for(graph, fields)


def test_pixal_crop_preview_uses_connected_roles_and_original_pixel_coordinates():
    graph = {"sheet": {"class_type": "LoadImage", "inputs": {"image": "sheet.png"}}}
    roles = ("front", "left", "back", "right")
    for index, role in enumerate(roles):
        graph[role] = {
            "class_type": "ImageCropV2",
            "inputs": {
                "image": ["sheet", 0],
                "crop_region": {"x": index * 80, "y": 20, "width": 100, "height": 160},
            },
        }
    graph["masked"] = {"class_type": "ImageCropToMask", "inputs": {"images": ["front", 0]}}
    graph["saved"] = {"class_type": "SaveImageAdvanced", "inputs": {"images": ["masked", 0]}}
    graph["pixal"] = {
        "class_type": "Pixal3DMultiViewConditioning",
        "inputs": {**{role: [role, 0] for role in roles}, "front": ["saved", 0]},
    }
    fields = [_field("sheet", "image", "image")]
    regions = image_crops_for(graph, fields)["sheet.image"]
    assert [(region.label, region.x) for region in regions] == [
        ("正面", 0),
        ("左侧", 80),
        ("背面", 160),
        ("右侧", 240),
    ]
    assert max(region.x + region.width for region in regions) == 340
    assert max(region.y + region.height for region in regions) == 180
    graph["right"]["inputs"]["image"] = ["unrelated", 0]
    assert not image_crops_for(graph, fields)


def test_output_choice_labels_and_mesh_guidance_preserve_engine_values():
    graph = {
        "moge": {"class_type": "MoGeRender", "inputs": {"output": "depth"}},
        "source": {"class_type": "PrimitiveInt", "inputs": {"value": 4096}},
        "bake": {"class_type": "BakeTextureFromVoxel", "inputs": {"texture_size": ["source", 0]}},
        "mesh": {"class_type": "DecimateMesh", "inputs": {"target_face_count": 300_000}},
    }
    choice = _field("moge", "output", "choice")
    choice.choices = ["mask", "depth", "custom"]
    choice.default = "depth"
    presentation = parameter_presentation_for(
        graph,
        [
            choice,
            _field("source", "value", "integer"),
            _field("mesh", "target_face_count", "integer"),
        ],
    )
    assert presentation[choice.id].choice_labels == {"mask": "遮罩", "depth": "深度图"}
    assert choice.default == "depth" and choice.choices == ["mask", "depth", "custom"]
    assert "材质" in (presentation["source.value"].guidance or "")
    assert "网格" in (presentation["mesh.target_face_count"].guidance or "")


def test_outpaint_links_the_four_padding_fields_to_their_source_image():
    directions = ("left", "top", "right", "bottom")
    graph = {
        "source": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "pad": {
            "class_type": "ImagePadForOutpaint",
            "inputs": {"image": ["source", 0], **dict.fromkeys(directions, 0)},
        },
    }
    fields = [
        _field("source", "image", "image"),
        *[_field("pad", side, "integer") for side in directions],
    ]
    outpaint = parameter_presentation_for(graph, fields)["source.image"].outpaint
    assert outpaint is not None
    assert (outpaint.left, outpaint.top, outpaint.right, outpaint.bottom) == tuple(
        f"pad.{side}" for side in directions
    )
    assert not parameter_presentation_for(graph, fields[:-1])

    graph["other_pad"] = graph["pad"]
    assert not parameter_presentation_for(graph, fields)


def test_mask_editor_binds_one_reference_to_one_red_channel_mask():
    graph = {
        "source": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "mask": {"class_type": "LoadImageMask", "inputs": {"image": "mask.png", "channel": "red"}},
        "paint": {
            "class_type": "InpaintModelConditioning",
            "inputs": {"pixels": ["source", 0], "mask": ["mask", 0]},
        },
    }
    channel = _field("mask", "channel", "choice").model_copy(update={"default": "red"})
    fields = [_field("source", "image", "image"), _field("mask", "image", "image"), channel]
    presentation = parameter_presentation_for(graph, fields)
    assert presentation["source.image"].mask is not None
    assert presentation["source.image"].mask.model_dump() == {
        "field_id": "mask.image",
        "channel_field_id": "mask.channel",
    }

    channel.default = "alpha"
    assert "source.image" not in parameter_presentation_for(graph, fields)
    channel.default = "red"
    graph["other"] = graph["source"]
    fields.append(_field("other", "image", "image"))
    graph["second_paint"] = {
        "class_type": "VAEEncodeForInpaint",
        "inputs": {"pixels": ["other", 0], "mask": ["mask", 0]},
    }
    assert not parameter_presentation_for(graph, fields)


def test_native_mask_through_vae_and_grow_is_bound_to_its_own_image_only():
    from comfyshop_api.services.parameter_features import native_mask_nodes

    graph = {
        "a": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
        "b": {"class_type": "LoadImage", "inputs": {"image": "other.png"}},
        "encode": {"class_type": "VAEEncode", "inputs": {"pixels": ["a", 0]}},
        "grow": {"class_type": "GrowMask", "inputs": {"mask": ["a", 1], "expand": 4}},
        "noise": {
            "class_type": "SetLatentNoiseMask",
            "inputs": {"samples": ["encode", 0], "mask": ["grow", 0]},
        },
    }
    loader = native_mask_nodes(graph)["a"]
    fields = [_field("a", "image", "image"), _field(loader, "image", "image")]
    mask = parameter_presentation_for(graph, fields)["a.image"].mask
    assert mask is not None and mask.field_id == loader + ".image" and mask.channel_field_id is None
    graph["encode"]["inputs"]["pixels"] = ["b", 0]
    assert not native_mask_nodes(graph)
    graph["grow"]["inputs"]["mask"] = ["grow", 0]
    assert not native_mask_nodes(graph)


def test_crop_editor_requires_one_direct_crop_with_four_scalar_inputs():
    graph = {
        "source": {"class_type": "LoadImage", "inputs": {"image": "sample.png"}},
        "crop": {"class_type": "ImageCrop", "inputs": {"image": ["source", 0]}},
    }
    names = ("x", "y", "width", "height")
    fields = [
        _field("source", "image", "image"),
        *[_field("crop", name, "integer") for name in names],
    ]
    crop = parameter_presentation_for(graph, fields)["source.image"].crop
    assert crop is not None and crop.model_dump() == {name: "crop." + name for name in names}
    assert not parameter_presentation_for(graph, fields[:-1])
    graph["other"] = graph["crop"]
    assert not parameter_presentation_for(graph, fields)


def test_placement_preserves_stack_order_and_rejects_unmatched_masks_or_branches():
    def node(kind, **inputs):
        return {"class_type": kind, "inputs": inputs}

    graph = {
        "base": node("LoadImage", image="background.png"),
        "a": node("LoadImage", image="a.png"),
        "b": node("LoadImage", image="b.png"),
        "join": node("JoinImageWithAlpha", image=["a", 0], alpha=["a", 1]),
        "scale": node("ImageScaleBy", image=["join", 0], scale_by=1.0),
        "rotate": node("ImageRotate", image=["scale", 0], rotation="none"),
        "split": node("SplitImageWithAlpha", image=["rotate", 0]),
        "alpha": node("InvertMask", mask=["split", 1]),
        "first": node(
            "ImageCompositeMasked",
            destination=["base", 0],
            source=["split", 0],
            mask=["alpha", 0],
            x=0,
            y=0,
            resize_source=False,
        ),
        "second": node(
            "ImageCompositeMasked",
            destination=["first", 0],
            source=["b", 0],
            x=12,
            y=8,
            resize_source=False,
        ),
    }
    fields = [
        *[_field(n, "image", "image") for n in ("a", "b", "base")],
        _field("scale", "scale_by", "number"),
        _field("rotate", "rotation", "choice"),
        *[
            _field(n, key, kind)
            for n in ("first", "second")
            for key, kind in (("x", "integer"), ("y", "integer"), ("resize_source", "boolean"))
        ],
    ]
    layers = parameter_presentation_for(graph, fields)["base.image"].layers
    assert [(layer.image, layer.scale, layer.rotation, layer.alpha) for layer in layers] == [
        ("a.image", "scale.scale_by", "rotate.rotation", True),
        ("b.image", None, None, False),
    ]
    graph["fork"] = graph["second"]
    assert not parameter_presentation_for(graph, fields)
    del graph["fork"]
    graph["alpha"]["inputs"]["mask"] = ["b", 1]
    assert not parameter_presentation_for(graph, fields)
