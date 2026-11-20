"""从平台冻结的图生成本次执行副本，并检查本机 ComfyUI 依赖。"""

from copy import deepcopy

from comfyshop_worker.catalog import asset_kind


class WorkflowError(Exception):
    pass


def prepare_bound_graph(
    original: dict, seeds: list[dict], assets: list[dict], uploaded: dict[str, str]
) -> dict:
    """在 `original` 的副本中绑定本次 `seeds` 和 `uploaded` 里的 ComfyUI 文件路径。

    `assets` 是节点输入到素材 ID 的绑定。绑定缺少对应上传文件时抛出 `WorkflowError`。
    """
    graph = deepcopy(original)
    for asset in assets:
        if asset["id"] not in uploaded:
            raise WorkflowError("素材尚未传入工作机")
        graph[asset["nodeId"]]["inputs"][asset["inputName"]] = uploaded[asset["id"]]
    for seed in seeds:
        graph[seed["nodeId"]]["inputs"][seed["inputName"]] = int(seed["value"])
    return graph


def preflight(graph: dict, object_info: dict) -> None:
    """比对当前节点目录，缺少节点或枚举选项时抛出 `WorkflowError`。"""
    missing = sorted({n["class_type"] for n in graph.values()} - object_info.keys())
    if missing:
        raise WorkflowError("缺少节点：" + "、".join(missing))
    missing_models = []
    for node in graph.values():
        schema = object_info[node["class_type"]].get("input", {})
        fields = {**schema.get("required", {}), **schema.get("optional", {})}
        for name, value in node["inputs"].items():
            definition = fields.get(name)
            if not definition or not isinstance(value, str):
                continue
            options = (
                definition[1] if len(definition) > 1 and isinstance(definition[1], dict) else {}
            )
            if asset_kind(node["class_type"], name, options):
                # Uploads arrive after inventory refresh. ComfyUI validates the
                # newly written file when it accepts the prompt.
                continue
            choices = definition[0] if definition else None
            if choices == "COMBO" and len(definition) > 1:
                choices = definition[1].get("options")
            if isinstance(choices, list) and value not in choices:
                missing_models.append(f"{node['class_type']}.{name}: {value}")
    if missing_models:
        raise WorkflowError("模型或选项不可用：" + "；".join(missing_models)[:1500])
