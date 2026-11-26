# MiniMax H3 Max 文生视频

根据提示词生成视频，可设置时长、分辨率、画面比例和提示词扩写。Atlas Cloud 模型 ID 为 `minimax/h3-max/text-to-video`。[模型 API 页](https://www.atlascloud.ai/zh/models/minimax/h3-max/text-to-video?tab=api)

## 官方参数

请求字段、枚举和供应商默认值见官方 OpenAPI 定义的 `components.schemas.Input`。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-max-text-to-video.json) · [官方请求示例](https://static.atlascloud.ai/model/example/minimax-h3-max-text-to-video.json)

| Atlas 参数         | 必填 | 默认值                         | 输入约定                                    |
| ------------------ | ---- | ------------------------------ | ------------------------------------------- |
| `model`            | 是   | `minimax/h3-max/text-to-video` | 工作机从 `execution.config.model` 取值      |
| `prompt`           | 是   | 由用户填写                     | 描述视频的文本，提交前须填写内容            |
| `duration`         | 是   | `8`                            | 5 至 15 秒，按整数枚举提交                  |
| `resolution`       | 是   | `768P`                         | `480P`、`768P`、`1440p-sr`、`4k-sr`         |
| `ratio`            | 否   | `1:1`                          | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | 否   | `false`                        | 布尔值，控制是否扩写提示词                  |

## Atlas Cloud 调用

向 `POST https://api.atlascloud.ai/api/v1/model/generateVideo` 发送 JSON，使用 `Authorization: Bearer <API_KEY>`。下面的请求显式选择 `16:9`。

```json
{
  "model": "minimax/h3-max/text-to-video",
  "prompt": "雨后清晨，镜头沿山间铁路缓慢推进。",
  "duration": 8,
  "resolution": "768P",
  "ratio": "16:9",
  "prompt_expansion": false
}
```

从提交响应读取 `data.id`，用同一密钥轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。生成完成后，从 `data.outputs` 获取视频地址。[Atlas Cloud 预测文档](https://www.atlascloud.ai/docs/en/predictions)

## ComfyShop 工作流

清单保存一份官方执行定义，标题、简介、标签和帮助放在按语言索引的 translations 字段中。[工作流清单与五种译文](workflow.json)

`parameterLayout` 使用 ComfyUI 表单已有的分组和说明。`fieldId` 对应 `fields[].name`，布局数组的顺序决定区内的展示顺序。`section` 可取 `default`、`advanced`、`hidden`，`help` 显示在字段旁的问号中。布局可用 `defaultValue` 覆盖字段的 `default`。本模型把扩写提示词放进高级分组。[参数与素材规则](../../../../../../../../docs/architecture.md#参数与素材)

维护账号可在工作流详情打开「编辑参数」，保存该版本的分组、顺序、名称、说明、控件和默认值。新任务使用保存后的默认值，已提交任务使用提交时保存的参数。导出工作流 JSON 包含当前版本的布局。

`execution.config.parameters` 的键是 Atlas 请求参数名，值是 ComfyShop 的字段名。`duration_seconds`、`aspect_ratio` 和 `expand_prompt` 分别映射到 Atlas 的 `duration`、`ratio` 和 `prompt_expansion`。可选字段有表单默认值时，工作机会把该值一并发送。

## 导入与同步

配置 `COMFYSHOP_SERVER_URL` 和 `COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL` 后，可在仓库根目录跑全量内置目录同步。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)

```sh
uv run --project integrations/official-worker --locked \
  comfyshop-official-worker sync
```

只导入本模型时，指定清单路径。

```sh
model_dir=integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/h3-max/text-to-video
uv run --project integrations/official-worker --locked \
  comfyshop-official-worker sync "$model_dir/workflow.json"
```

目录用 `key` 识别工作流，字段、布局和执行配置相同会复用版本。[同步实现](../../../../../__main__.py)
