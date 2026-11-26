from comfyshop_api.schemas import AssetRead, MediaRead
from comfyshop_api.services.result_comparisons import output_comparisons


def test_comparison_follows_exact_output_geometry_and_readable_assets():
    asset = AssetRead(
        id="sample",
        filename="a.png",
        sha256="digest",
        size=50,
        content_type="image/png",
        media=MediaRead(src="/sample", width=100, height=80),
    )
    graph = {
        "a": {"class_type": "LoadImage", "inputs": {"image": "__comfyshop_asset__:sample"}},
        "b": {
            "class_type": "ImageCrop",
            "inputs": {"image": ["a", 0], "x": 15, "y": 20, "width": 95, "height": 30},
        },
        "c": {
            "class_type": "ImageCompositeMasked",
            "inputs": {"destination": ["b", 0], "source": ["other", 0]},
        },
        "d": {"class_type": "ImageUpscaleWithModel", "inputs": {"image": ["c", 0]}},
        "e": {"class_type": "SaveImage", "inputs": {"images": ["d", 0]}},
        "other": {"class_type": "LoadImage", "inputs": {"image": "__comfyshop_asset__:unreadable"}},
        "unknown": {"class_type": "SaveImage", "inputs": {"images": ["other", 0]}},
    }
    mapping = output_comparisons(graph, [asset])
    assert set(mapping) == {"e"}
    assert mapping["e"].model_dump() == dict(
        asset_id="sample", width=85, height=30, x=-15, y=-20, uniform_upscale=True
    )
    assert not output_comparisons(graph, [])
    graph["c"]["inputs"]["destination"] = ["c", 0]
    assert not output_comparisons(graph, [asset])
    graph["c"]["inputs"]["destination"] = ["a", 1]
    assert not output_comparisons(graph, [asset])
