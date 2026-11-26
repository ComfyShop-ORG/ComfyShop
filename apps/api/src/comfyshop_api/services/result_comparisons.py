"""从提交时的执行图追溯成品的底图与坐标，不依赖工作机当前的目录或表单。"""

from comfyshop_api.schemas import AssetRead, OutputComparison
from comfyshop_api.services.inputs import ASSET_PLACEHOLDER_PREFIX


def _reference(graph: dict, link: object, assets: dict[str, AssetRead]) -> OutputComparison | None:
    geometry = None
    upscale = False
    visited = set()
    while (
        isinstance(link, list)
        and len(link) == 2
        and isinstance(link[0], str)
        and type(link[1]) is int
        and link[1] == 0
        and link[0] not in visited
    ):
        visited.add(link[0])
        node = graph.get(link[0])
        if not isinstance(node, dict) or not isinstance(inputs := node.get("inputs"), dict):
            break
        kind = node.get("class_type")
        if kind == "LoadImage":
            source = inputs.get("image")
            if not isinstance(source, str) or not source.startswith(ASSET_PLACEHOLDER_PREFIX):
                break
            asset = assets.get(source.removeprefix(ASSET_PLACEHOLDER_PREFIX))
            if not asset or not (width := asset.media.width) or not (height := asset.media.height):
                break
            x = y = 0
            if geometry:
                transform, values = geometry
                if transform == "ImageCrop":
                    x, y, w, h = values
                    if x >= width or y >= height or min(w, h) < 1:
                        break
                    width, height = min(w, width - x), min(h, height - y)
                    x, y = -x, -y
                else:
                    x, y, right, bottom = values
                    width, height = width + x + right, height + y + bottom
            return OutputComparison(
                asset_id=asset.id, width=width, height=height, x=x, y=y, uniform_upscale=upscale
            )
        if kind == "ImageCompositeMasked":
            link = inputs.get("destination")
            continue
        if kind == "ImageUpscaleWithModel" and geometry is None:
            upscale = True
        elif kind in ("ImageCrop", "ImagePadForOutpaint") and geometry is None:
            keys = (
                ("x", "y", "width", "height")
                if kind == "ImageCrop"
                else ("left", "top", "right", "bottom")
            )
            values = [v for key in keys if type(v := inputs.get(key)) is int and v >= 0]
            if len(values) != len(keys):
                break
            geometry = (kind, values)
        else:
            break
        link = inputs.get("image")
    return None


def output_comparisons(
    graph: dict, readable_assets: list[AssetRead]
) -> dict[str, OutputComparison]:
    assets = {asset.id: asset for asset in readable_assets if asset.media.kind == "image"}
    return {
        node_id: source
        for node_id, node in graph.items()
        if isinstance(node, dict)
        and node.get("class_type") in {"SaveImage", "PreviewImage"}
        and isinstance(inputs := node.get("inputs"), dict)
        and (source := _reference(graph, inputs.get("images"), assets)) is not None
    }
