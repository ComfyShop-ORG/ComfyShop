from copy import deepcopy

import pytest
from comfyshop_worker_protocol.catalog import make_catalog

from comfyshop_worker.comfy import history_outputs
from comfyshop_worker.graph import WorkflowError, preflight, prepare_bound_graph


def test_successful_audio_is_collected_from_comfy_history():
    descriptor = {"filename": "music.flac", "type": "output", "subfolder": "audio"}
    assert history_outputs(
        {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"10": {"audio": [descriptor]}},
        }
    ) == [{**descriptor, "outputNodeId": "10", "outputSlot": "audio", "outputIndex": 0}]


def test_glb_collection_keeps_the_saved_original_and_skips_the_temp_copy():
    model = {"filename": "model.glb", "type": "output", "subfolder": "3d"}
    assert history_outputs(
        {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"9": {"3d": [{**model, "type": "temp"}]}, "10": {"3d": [model]}},
        }
    ) == [{**model, "outputNodeId": "10", "outputSlot": "3d", "outputIndex": 0}]


@pytest.mark.parametrize(
    ("node", "field", "kind", "suffix"),
    [("LoadAudio", "audio", "audio", "flac"), ("Load3DAdvanced", "model_file", "3d", "glb")],
)
def test_uploaded_fields_do_not_require_a_preexisting_work_machine_file(node, field, kind, suffix):
    info = {node: {"input": {"required": {field: [[f"existing.{suffix}"]]}}}}
    spec = make_catalog(info)["nodes"][node]["inputs"][field]
    assert spec["kind"] == kind and spec["choices"] == []
    preflight(
        {"1": {"class_type": node, "inputs": {field: f"ComfyShop/task/reference.{suffix}"}}},
        info,
    )


def test_bound_graph_applies_api_seed_without_changing_frozen_inputs_or_links():
    graph = {
        "text": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {"prompt": "frozen positive", "negative_prompt": "frozen negative"},
        },
        "sample": {
            "class_type": "KSampler",
            "inputs": {"positive": ["text", 0], "negative": ["text", 1], "seed": 42, "steps": 16},
        },
    }
    original = deepcopy(graph)
    seeds = [{"nodeId": "sample", "inputName": "seed", "value": "53"}]
    prepared = prepare_bound_graph(graph, seeds, [], {})
    assert graph == original
    assert prepared["text"] == graph["text"]
    assert prepared["sample"]["inputs"]["seed"] == 53
    assert prepared["sample"]["inputs"]["positive"] == ["text", 0]
    assert prepared["sample"]["inputs"]["steps"] == 16
    with pytest.raises(WorkflowError, match="缺少节点"):
        preflight(prepared, {})
    with pytest.raises(WorkflowError, match="模型或选项"):
        preflight(
            {"1": {"class_type": "Loader", "inputs": {"model": "absent"}}},
            {"Loader": {"input": {"required": {"model": [["installed"]]}}}},
        )


def test_terminal_signal_or_empty_outputs_cannot_fake_success():
    with pytest.raises(WorkflowError, match="未确认"):
        history_outputs({"status": {"completed": True, "status_str": "error"}})
    with pytest.raises(WorkflowError, match="out of memory"):
        history_outputs(
            {
                "status": {
                    "status_str": "error",
                    "messages": [["execution_error", {"exception_message": "out of memory"}]],
                }
            }
        )
    with pytest.raises(WorkflowError, match="未输出"):
        history_outputs({"status": {"completed": True, "status_str": "success"}, "outputs": {}})
    image = {"filename": "a.png", "subfolder": "", "type": "output"}
    video = {"filename": "v.mp4", "subfolder": "", "type": "output"}
    assert history_outputs(
        {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"1": {"images": [image, image]}, "2": {"videos": [video]}},
        }
    ) == [
        {**image, "outputNodeId": "1", "outputSlot": "images", "outputIndex": 0},
        {**video, "outputNodeId": "2", "outputSlot": "videos", "outputIndex": 1},
    ]


def test_bound_asset_and_large_seed_remain_exact_without_mutating_snapshot():
    graph = {
        "image": {"class_type": "LoadImage", "inputs": {"image": "__comfyshop_asset__:asset"}},
        "sample": {"class_type": "KSampler", "inputs": {"seed": 2**64 - 1}},
    }
    frozen_seed = 2**64 - 2
    seeds = [{"nodeId": "sample", "inputName": "seed", "value": str(frozen_seed)}]
    assets = [{"id": "asset", "nodeId": "image", "inputName": "image"}]
    result = prepare_bound_graph(graph, seeds, assets, {"asset": "ComfyShop/task/asset.png"})
    assert result["sample"]["inputs"]["seed"] == frozen_seed
    assert result["image"]["inputs"]["image"] == "ComfyShop/task/asset.png"
    assert graph["sample"]["inputs"]["seed"] == 2**64 - 1
    with pytest.raises(WorkflowError, match="素材"):
        prepare_bound_graph(graph, seeds, assets, {})


def test_freshly_uploaded_file_is_not_rejected_by_old_file_listing():
    preflight(
        {"1": {"class_type": "LoadImage", "inputs": {"image": "ComfyShop/new.png"}}},
        {"LoadImage": {"input": {"required": {"image": [["old.png"], {"image_upload": True}]}}}},
    )
