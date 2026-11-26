"""Run the official work machine or import its workflow files."""

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import Iterator
from functools import partial
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

import httpx
import uvicorn
from comfyshop_worker_protocol.definition import OFFICIAL
from comfyshop_worker_protocol.logging import logger, worker_logging
from comfyshop_worker_protocol.platform import Platform
from pydantic import ValidationError

from .atlas_cloud import (
    ADAPTER,
    ATLAS_ROOT,
    Atlas,
    AtlasSpec,
    ChoiceSlots,
    ImageReferenceObjects,
    MediaBinding,
    MediaObjectArray,
    VideoKeyframes,
)
from .quotes import quote_app, quote_atlas
from .runner import DEFAULT_MAX_CONCURRENCY, Runner


def _workflow(path: Traversable) -> dict:
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
        execution = graph["execution"]
        if (
            graph["format"] != "service"
            or graph["workerKind"] != "official"
            or execution["adapter"] != ADAPTER
        ):
            raise ValueError("工作机不支持此格式或适配器")
        spec = AtlasSpec.model_validate(execution["config"])
        output_kind = execution["outputKind"]
        if spec.operation != output_kind and (spec.operation, output_kind) not in {
            ("image", "3d"),
            ("audio", "text"),
        }:
            raise ValueError("成品类型与生成接口不一致")
        if spec.return_voice_result and "text" not in execution.get("additionalOutputKinds", []):
            raise ValueError("音色编号需要文本成品类型")
        fields = {field["name"]: field["kind"] for field in graph["fields"]}
        scalar_fields = {
            name
            for name, kind in fields.items()
            if kind in {"string", "integer", "number", "boolean", "choice"}
        }
        if set(spec.parameters.values()) - scalar_fields or any(
            set(bindings.values()) - scalar_fields for bindings in spec.parameter_objects.values()
        ):
            raise ValueError("生成参数必须映射到已声明的字段")
        if any(fields.get(name) != "string" for name in spec.parameter_overrides.values()):
            raise ValueError("覆写值必须映射到已声明的文本字段")
        bounded_fields = {spec.parameters[name] for name in spec.choice_bounds}
        if any(
            field["kind"] not in {"integer", "number"}
            and not (
                field["kind"] == "choice"
                and field.get("choices")
                and all(type(value) in (int, float) for value in field["choices"])
            )
            for field in graph["fields"]
            if field["name"] in bounded_fields
        ):
            raise ValueError("选项范围必须映射到已声明的数值字段")
        if spec.media_bitmask is not None:
            name = spec.parameters[spec.media_bitmask.parameter]
            if fields.get(name) != "string":
                raise ValueError("素材位置编码必须映射到文本字段")
        json_parameters = set(spec.json_object_parameters) | spec.lora_parameters.keys()
        if any(fields.get(spec.parameters[name]) != "string" for name in json_parameters):
            raise ValueError("JSON 参数必须映射到文本字段")
        if (
            spec.kling_storyboard_field is not None
            and fields.get(spec.kling_storyboard_field) != "string"
        ) or (
            spec.kling_elements is not None and fields.get(spec.kling_elements.field) != "string"
        ):
            raise ValueError("分镜方案与主体引用必须映射到文本字段")
        if (
            spec.composition_plan_field is not None
            and fields.get(spec.composition_plan_field) != "string"
        ):
            raise ValueError("分段方案必须映射到文本字段")
        if spec.dialogue is not None and any(
            fields.get(name) != "string"
            for name in (spec.dialogue.field, spec.dialogue.custom_voice_field)
        ):
            raise ValueError("对话与自定义音色必须映射到文本字段")
        if (
            spec.color_palette_field is not None
            and fields.get(spec.color_palette_field) != "string"
        ):
            raise ValueError("调色板必须映射到文本字段")
        if any(
            fields.get(option.field) != "boolean"
            for binding in spec.choice_arrays.values()
            if not isinstance(binding, ChoiceSlots)
            for option in binding.options
        ):
            raise ValueError("数组选项必须映射到已声明的布尔字段")
        if any(
            fields.get(name) != "choice"
            for binding in spec.choice_arrays.values()
            if isinstance(binding, ChoiceSlots)
            for name in binding.fields
        ):
            raise ValueError("数组选项槽位必须映射到已声明的枚举字段")
        if any(
            fields.get(binding.field) != "string"
            and (binding.max_items != 1 or fields.get(binding.field) != "choice")
            for binding in spec.text_arrays.values()
        ):
            raise ValueError("文本数组必须映射到文本字段，单项列表也可使用枚举字段")
        for binding in spec.reference_arrays.values():
            if isinstance(binding, VideoKeyframes):
                if any(
                    fields.get(slot.fields[0]) != "image"
                    or fields.get(slot.url_field) != "string"
                    or fields.get(slot.index_field) != "integer"
                    for slot in binding.slots
                ):
                    raise ValueError("关键帧必须映射到图片、文本地址与整数帧号字段")
                continue
            if isinstance(binding, ImageReferenceObjects):
                if any(
                    fields.get(slot.fields[0]) != "image"
                    or fields.get(slot.external_sources_field or "") != "string"
                    or fields.get(slot.reference_type_field) != "choice"
                    or fields.get(slot.reference_name_field) != "string"
                    for slot in binding.slots
                ):
                    raise ValueError("图片引用必须映射到图片、文本地址、类型和名称字段")
                continue
            for slot in binding.slots:
                if (
                    any(fields.get(name) not in {"choice", "string"} for name in slot.values)
                    or fields.get(slot.asset.inline_field) != "boolean"
                    or any(fields.get(name) != slot.asset.kind for name in slot.asset.fields)
                ):
                    raise ValueError("参考来源必须映射到类型一致的表单字段")
        if spec.image_subjects is not None and any(
            fields.get(slot.id_field) != "string"
            or fields.get(slot.images.external_sources_field or "") != "string"
            or any(fields.get(name) != "image" for name in slot.images.fields)
            for slot in spec.image_subjects.slots
        ):
            raise ValueError("图片主体必须映射到类型一致的表单字段")
        for rule in spec.enabled_by.values():
            parameter = rule if isinstance(rule, str) else rule.parameter
            kind = fields.get(spec.parameters.get(parameter, ""))
            fixed_value = spec.fixed.get(parameter)
            valid = (
                kind == "boolean" or type(fixed_value) is bool
                if isinstance(rule, str) or isinstance(rule.equals, bool)
                else kind in {"choice", "string"} or isinstance(fixed_value, str)
            )
            if not valid:
                raise ValueError("依赖条件的字段类型无效")
        if any(
            fields.get(name) != slots.kind
            for binding in spec.media.values()
            for slots in (binding.groups if isinstance(binding, MediaObjectArray) else (binding,))
            for name in slots.fields
        ):
            raise ValueError("素材参数必须映射到类型一致的表单字段")
        if any(
            fields.get(name) != "string"
            for binding in spec.media.values()
            for group in (binding.groups if isinstance(binding, MediaObjectArray) else (binding,))
            for name in (
                group.ordered_source_fields
                if isinstance(group, MediaBinding) and group.ordered_source_fields
                else (group.external_sources_field,)
            )
            if name is not None
        ):
            raise ValueError("素材地址必须映射到已声明的文本字段")
        if any(
            isinstance(binding, MediaBinding)
            and binding.video_clip is not None
            and any(
                fields.get(name) not in {"integer", "number"}
                for name in (
                    binding.video_clip.start,
                    binding.video_clip.ends,
                    binding.video_clip.fps,
                )
                if name is not None
            )
            for binding in spec.media.values()
        ):
            raise ValueError("视频剪辑参数必须映射到已声明的数值字段")
        return {"name": graph["name"], "category": graph["category"], "graph": graph}
    except ValidationError as error:
        details = error.json(include_input=False, include_context=False, include_url=False)
        raise ValueError(f"{path.name} 的工作流执行配置无效\n{details}") from None
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{path.name} 的工作流配置无效：{error}") from None


async def _register_owner(server_url: str) -> None:
    password = os.environ.get("COMFYSHOP_OFFICIAL_OWNER_PASSWORD")
    if not password:
        raise ValueError("首次创建维护账号时，请设置 COMFYSHOP_OFFICIAL_OWNER_PASSWORD。")
    username = os.environ.get("COMFYSHOP_OFFICIAL_OWNER") or "ComfyShop"
    origin = server_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{origin}/api/v1/auth/register",
            headers={"Origin": origin},
            json={"username": username, "password": password},
        )
        if response.status_code != 409:
            response.raise_for_status()


def _cover_path(directory: Traversable) -> Traversable | None:
    for name in ("cover.webp", "cover.png"):
        path = directory.joinpath(name)
        if path.is_file():
            return path
    return None


def _builtin_files(
    directory: Traversable,
) -> Iterator[tuple[Traversable, Traversable | None]]:
    cover = _cover_path(directory)
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.is_dir():
            yield from _builtin_files(path)
        elif path.name == "workflow.json" and path.is_file():
            yield path, cover


async def _sync(
    server_url: str, token: str, paths: list[Path], *, init_owner: bool, publish: bool
) -> None:
    workflows_root = files("comfyshop_official_worker").joinpath("workflows")
    builtins = list(_builtin_files(workflows_root))
    if paths:
        cover_by_key = {
            json.loads(path.read_text(encoding="utf-8"))["key"]: cover
            for path, cover in builtins
            if cover is not None
        }
        workflows = [_workflow(path) for path in paths]
        imports = [(workflow, cover_by_key.get(workflow["graph"]["key"])) for workflow in workflows]
    else:
        imports = [(_workflow(path), cover) for path, cover in builtins]
    if not imports:
        raise ValueError("没有找到可同步的工作流")
    if len({workflow["graph"]["key"] for workflow, _ in imports}) != len(imports):
        raise ValueError("同步清单中有重复的官方工作流标识")
    cover_targets: list[tuple[Traversable, str]] = []
    drafts = []
    publish_params = {"initialize": "true"} if publish else {}
    logger.info(
        "开始同步官方工作流",
        workflow_count=len(imports),
        initialize=init_owner,
        publish=publish,
    )
    async with httpx.AsyncClient(
        base_url=server_url.rstrip("/") + "/api/v1/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    ) as platform:
        for workflow, cover in imports:
            response = await platform.post("workflows", params=publish_params, json=workflow)
            # 对已通过官方令牌认证的导入，维护账号缺失时平台返回 403。
            if init_owner and response.status_code == 403:
                logger.debug("开始注册官方工作流维护账号")
                await _register_owner(server_url)
                init_owner = False
                response = await platform.post("workflows", params=publish_params, json=workflow)
            response.raise_for_status()
            draft = response.json()
            drafts.append(draft)
            logger.debug("官方工作流已同步", workflow_id=draft["id"])
            if cover is not None:
                cover_targets.append((cover, draft["id"]))
        for cover, workflow_id in cover_targets:
            data = cover.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            response = await platform.put(
                f"worker/official/workflow-covers/{sha256}",
                params={"workflow_id": workflow_id},
                headers={"Content-Type": "application/octet-stream"},
                content=data,
            )
            response.raise_for_status()
            logger.debug("默认封面已同步", workflow_id=workflow_id)
    logger.info("官方工作流同步完成", workflow_count=len(drafts), cover_count=len(cover_targets))
    for draft in drafts:
        print(
            json.dumps(
                {
                    "workflowId": draft["id"],
                    "versionId": draft["versionId"],
                    "version": draft["version"],
                },
                ensure_ascii=False,
            )
        )


async def _run(
    server_url: str,
    token: str,
    atlas_key: str,
    max_concurrency: int,
    log_level: str,
    quote_port: int | None,
) -> None:
    async with (
        Platform(server_url, token) as platform,
        httpx.AsyncClient(
            base_url=ATLAS_ROOT, headers={"Authorization": f"Bearer {atlas_key}"}, timeout=60
        ) as provider,
        httpx.AsyncClient(timeout=60, follow_redirects=True) as downloads,
    ):
        atlas = Atlas(provider)
        runner = Runner(platform, atlas, downloads, max_concurrency=max_concurrency)
        logger.info(
            "官方工作机已启动",
            adapter=ADAPTER,
            log_level=log_level,
            max_concurrency=max_concurrency,
        )
        if quote_port is None:
            await runner.run()
            return
        server = uvicorn.Server(
            uvicorn.Config(
                quote_app({ADAPTER: partial(quote_atlas, atlas)}, token),
                host="0.0.0.0",  # noqa: S104 - on the internal worker network
                port=quote_port,
                access_log=False,
                log_config=None,
                timeout_graceful_shutdown=5,
            )
        )
        async with asyncio.TaskGroup() as group:
            work = group.create_task(runner.run())
            try:
                await server.serve()
            finally:
                work.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(prog="comfyshop-official-worker")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="领取并执行官方任务")
    run.add_argument(
        "--quote-port",
        type=int,
        default=os.environ.get("COMFYSHOP_OFFICIAL_WORKER_QUOTE_PORT") or None,
        help="仅内网使用的报价端口，也可用 COMFYSHOP_OFFICIAL_WORKER_QUOTE_PORT 设置",
    )
    run.add_argument(
        "--max-concurrency",
        type=int,
        default=os.environ.get("COMFYSHOP_OFFICIAL_WORKER_MAX_CONCURRENCY")
        or DEFAULT_MAX_CONCURRENCY,
        help=f"每个实例同时执行的生成次数上限，可用 COMFYSHOP_OFFICIAL_WORKER_MAX_CONCURRENCY 设置，默认 {DEFAULT_MAX_CONCURRENCY}",
    )
    sync = commands.add_parser("sync", help="同步工作流")
    sync.add_argument(
        "--init-owner", action="store_true", help="按需注册维护账号，默认发布初始工作流"
    )
    sync.add_argument("--draft", action="store_true", help="仅导入为维护账号的草稿")
    sync.add_argument("paths", nargs="*", type=Path, help="省略时上传内置工作流")
    args = parser.parse_args()
    server_url = os.environ.get("COMFYSHOP_SERVER_URL", "http://127.0.0.1:8688")
    token = os.environ.get("COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL")
    if not token:
        parser.error("请设置 COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL")
    try:
        with worker_logging(OFFICIAL.kind) as level:
            _dispatch(args, parser, server_url, token, level)
    except ValueError as error:
        parser.error(str(error))


def _dispatch(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    server_url: str,
    token: str,
    level: str,
) -> None:
    try:
        if args.command == "sync":
            asyncio.run(
                _sync(
                    server_url,
                    token,
                    args.paths,
                    init_owner=args.init_owner,
                    publish=args.init_owner and not args.draft,
                )
            )
        else:
            atlas_key = os.environ.get("ATLAS_CLOUD_API_KEY")
            if not atlas_key:
                parser.error("请设置 ATLAS_CLOUD_API_KEY")
            if args.quote_port is not None and not 1 <= args.quote_port <= 65535:
                parser.error("报价端口必须介于 1 和 65535")
            asyncio.run(
                _run(server_url, token, atlas_key, args.max_concurrency, level, args.quote_port)
            )
    except httpx.HTTPStatusError as error:
        logger.error(
            "官方工作机命令失败", command=args.command, http_status=error.response.status_code
        )
        parser.exit(1)
    except (OSError, httpx.HTTPError) as error:
        logger.error("官方工作机命令失败", command=args.command, error_type=type(error).__name__)
        parser.exit(1)
    except ValueError as error:
        logger.error("官方工作机命令失败，{}", error, command=args.command)
        parser.exit(1)
    except KeyboardInterrupt:
        logger.info("已停止官方工作机命令", command=args.command)


if __name__ == "__main__":
    main()
