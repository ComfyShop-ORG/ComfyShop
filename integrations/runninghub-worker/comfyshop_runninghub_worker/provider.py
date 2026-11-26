"""RunningHub workflow-by-ID API and native ComfyUI widget metadata."""

import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from comfyshop_worker_protocol import TaskStage
from comfyshop_worker_protocol.catalog import asset_kind, make_catalog
from comfyshop_worker_protocol.definition import Source, SubmissionRejected, WorkerDefinition

SITES = {"cn": "www.runninghub.cn", "ai": "www.runninghub.ai"}


def credential_input(name: str) -> bool:
    return bool(
        re.search(
            r"(?:^|_)(?:api_?key|(?:access_|auth_|bearer_)token|secret|password|authorization|credential)$",
            name,
            re.I,
        )
    )


class ProviderError(ValueError):
    pass


def reference_id(reference: str, scope: str) -> str:
    ref = reference.strip()
    if re.fullmatch(r"[0-9]{1,32}", ref):
        return ref
    try:
        url = urlsplit(ref)
        if url.scheme == "https" and url.netloc in {SITES[scope], SITES[scope][4:]}:
            path = (
                url.fragment.split("?", 1)[0]
                if url.path in {"", "/"} and url.fragment.startswith("/")
                else url.path
            )
            if match := re.fullmatch(r"/(?:workflow|post)/([0-9]{1,32})/?", path):
                return match[1]
    except ValueError:
        pass
    raise ProviderError("请输入所选站点的 RunningHub 工作流链接或数字 ID")


class Hub:
    def __init__(self, http: httpx.AsyncClient, scope: str, key: str):
        self.http, self.key, self.root = http, key, "https://" + SITES[scope]

    async def post(self, path: str, body: dict) -> dict:
        response = await self.http.post(
            self.root + path,
            headers={"Authorization": "Bearer " + self.key},
            json={"apiKey": self.key, **body},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or type(data.get("code")) is not int:
            raise ProviderError("RunningHub 响应格式无效")
        return data

    def data(self, result: dict):
        if result["code"] != 0:
            detail = str(result.get("msg") or "请求失败").replace(self.key, "[redacted]")[:180]
            raise ProviderError(f"RunningHub 请求失败（{result['code']}）{detail}")
        return result.get("data")

    async def graph(self, reference: str) -> dict:
        try:
            data = self.data(
                await self.post("/api/openapi/getJsonApiFormat", {"workflowId": reference})
            )
            value = data.get("prompt") if isinstance(data, dict) else None
            graph = json.loads(value) if isinstance(value, str) else value
            if (
                not isinstance(graph, dict)
                or not graph
                or len(graph) > 5000
                or not all(
                    isinstance(n, dict)
                    and isinstance(n.get("class_type"), str)
                    and isinstance(n.get("inputs"), dict)
                    for n in graph.values()
                )
            ):
                raise ValueError()
            if any(
                credential_input(name) and isinstance(value, str) and value.strip()
                for node in graph.values()
                for name, value in node["inputs"].items()
            ):
                raise ProviderError("工作流内含私有凭据，请移除后重新导入")
            return graph
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise ProviderError(
                "无法读取 RunningHub 工作流，请核对站点、Key 和工作流权限"
            ) from None

    async def native_catalog(self) -> dict:
        # httpx logs full request URLs. Use the transport directly for this credential-bearing native route.
        req = httpx.Request(
            "GET",
            self.root + "/proxy/" + quote(self.key, safe="") + "/object_info",
            extensions={"timeout": dict.fromkeys(("connect", "read", "write", "pool"), 8.0)},
        )
        try:
            async with httpx.AsyncHTTPTransport() as transport:
                res = await transport.handle_async_request(req)
                try:
                    if res.status_code != 200:
                        return {}
                    raw = bytearray()
                    async for chunk in res.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 32 * 1024 * 1024:
                            return {}
                    info = json.loads(raw)
                    return info if isinstance(info, dict) else {}
                finally:
                    await res.aclose()
        except (ValueError, httpx.HTTPError):
            return {}

    async def upload(self, path: Path, name: str, mime: str) -> dict:
        with path.open("rb") as content:
            res = await self.http.post(
                self.root + "/openapi/v2/media/upload/binary",
                headers={"Authorization": "Bearer " + self.key},
                files={"file": (name, content, mime)},
            )
        res.raise_for_status()
        data = self.data(res.json())
        if not isinstance(data, dict) or not data.get("fileName"):
            raise ProviderError("RunningHub 未返回上传的文件名")
        return data

    async def submit(self, ref: str, values: list[dict]) -> str:
        try:
            body = await self.post(
                "/task/openapi/create", {"workflowId": ref, "nodeInfoList": values}
            )
            if body["code"] in {
                301,
                380,
                412,
                415,
                416,
                421,
                433,
                435,
                436,
                801,
                802,
                803,
                806,
                810,
                811,
                812,
                1002,
                1007,
            }:
                detail = str(body.get("msg") or "请求未受理").replace(self.key, "[redacted]")[:180]
                raise SubmissionRejected(f"RunningHub 拒绝了提交（{body['code']}）{detail}")
            data = body.get("data") if body["code"] == 0 else None
            task_id = data.get("taskId") if isinstance(data, dict) else None
            if type(task_id) in (int, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", str(task_id)):
                return str(task_id)
        except SubmissionRejected:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        raise ProviderError("提交结果待核对，请查看 RunningHub 任务记录")

    async def outputs(self, task_id: str) -> TaskStage | list:
        body = await self.post("/task/openapi/outputs", {"taskId": task_id})
        if body["code"] == 813:
            return "cloud_queued"
        if body["code"] == 804:
            return "cloud_running"
        if body["code"] in {500, 1000, 1003, 1005, 1010, 1011, 1012}:
            return "cloud_waiting"
        data = self.data(body)
        if (
            not isinstance(data, list)
            or not data
            or not all(
                isinstance(item, dict) and isinstance(item.get("fileUrl"), str) for item in data
            )
        ):
            raise ProviderError("RunningHub 未返回成品")
        return data


def url_image(kind: str, name: str) -> bool:
    compact = kind.lower().replace("_", "")
    return "loadimage" in compact and "url" in compact and name in {"url", "image", "image_url"}


def widget_catalog(graph: dict, info: dict) -> tuple[dict, bool, tuple]:
    catalog = {}
    missing = False
    assets = []
    native_widgets = {}
    for node_id, node in graph.items():
        kind = node["class_type"]
        if kind not in catalog:
            native = info.get(kind)
            definition = {}
            if isinstance(native, dict) and isinstance(native.get("input"), dict):
                try:
                    definition = make_catalog({kind: native})["nodes"][kind]
                    native_widgets[kind] = definition["inputs"]
                except (TypeError, ValueError, AttributeError):
                    pass
            catalog[kind] = {
                "title": definition.get("title", kind),
                "outputNode": definition.get("outputNode", kind in {"SaveImage", "PreviewImage"}),
                "inputs": {},
            }
        known = kind in native_widgets
        missing |= not known
        for name, value in node["inputs"].items():
            if type(value) not in (str, bool, int, float) or credential_input(name):
                continue
            spec = None
            if known:
                spec = native_widgets[kind].get(name)
            elif media := asset_kind(kind, name, {}):
                spec = {"kind": media}
            else:
                scalar = {str: "string", bool: "boolean", int: "integer", float: "number"}[
                    type(value)
                ]
                if kind in {"KSampler", "KSamplerAdvanced"} and name in {"cfg", "denoise"}:
                    scalar = "number"
                spec = {"kind": scalar, "multiline": name in {"text", "prompt", "negative_prompt"}}
            if url_image(kind, name):
                spec = {"kind": "image"}
            if spec:
                if spec["kind"] == "choice" and (
                    name
                    in {
                        "ckpt_name",
                        "unet_name",
                        "lora_name",
                        "clip_name",
                        "vae_name",
                        "model_name",
                    }
                    or any(
                        isinstance(v, str)
                        and v.lower().endswith((".safetensors", ".ckpt", ".gguf", ".pth", ".onnx"))
                        for v in spec["choices"]
                    )
                ):
                    spec = {"kind": "string"}
                catalog[kind]["inputs"][name] = spec
                if spec["kind"] in {"image", "audio", "video", "3d"} and value:
                    assets.append((node_id, name))
    return catalog, missing, tuple(assets)


async def load_reference(scope: str, key: str, reference: str) -> Source:
    ref = reference_id(reference, scope)
    async with httpx.AsyncClient(timeout=30) as http:
        hub = Hub(http, scope, key)
        graph = await hub.graph(ref)
        catalog, limited, assets = widget_catalog(graph, await hub.native_catalog())
        return Source(ref, graph, catalog, limited, assets)


async def cancel(scope: str, key: str, task_id: str) -> None:
    async with httpx.AsyncClient(timeout=8) as http:
        hub = Hub(http, scope, key)
        hub.data(await hub.post("/task/openapi/cancel", {"taskId": task_id}))


def executor(http: httpx.AsyncClient, auth: dict):
    from .worker import Adapter

    return Adapter(http, auth)


definition = WorkerDefinition(
    kind="runninghub",
    label="RunningHub",
    connection="account",
    form="nodes",
    executor=executor,
    sites={k: v[4:] for k, v in SITES.items()},
    load_reference=load_reference,
    cancel=cancel,
    output_node="outputs",
)
