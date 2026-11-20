from copy import deepcopy

import pytest

from comfyshop_worker.comfy import history_outputs
from comfyshop_worker.graph import WorkflowError, preflight, prepare_bound_graph


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
