# FLUX 3 图像编辑

用提示词编辑 1 至 10 张参考图，可按图片编号说明各自的作用。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/edit`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/edit)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                                               | 必填 | 默认值                          | 输入约定                                                                                                    |
| ------------------------- | ------------------------------------------------------------ | ---- | ------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`                                     | 是   | `black-forest-labs/flux-3/edit` | 工作机从执行配置读取                                                                                        |
| `prompt`                  | `prompt`                                                     | 是   | —                               | 编辑指令，按 `image 1` 至 `image 10` 引用图片                                                               |
| `reference_images`        | `reference_image_1` 至 `reference_image_10`，`image_sources` | 是   | —                               | 1 至 10 张参考图，上传或公开 URL                                                                            |
| `aspect_ratio`            | `aspect_ratio`                                               | 否   | `auto`                          | `auto`、`21:9`、`2:1`、`16:9`、`3:2`、`7:5`、`4:3`、`5:4`、`1:1`、`4:5`、`3:4`、`5:7`、`2:3`、`9:16`、`1:2` |
| `resolution`              | `resolution`                                                 | 否   | `1k`                            | `768sq`、`1k`、`2k`、`4k`                                                                                   |
| `enable_prompt_expansion` | `enable_prompt_expansion`                                    | 否   | `false`                         | 将短提示词扩写为更完整的描述                                                                                |
| `output_format`           | `output_format`                                              | 否   | `jpeg`                          | `jpeg` 或 `png`                                                                                             |
| `safety_tolerance`        | `safety_tolerance`                                           | 否   | `2`                             | 整数 0 至 4，0 最严格                                                                                       |

参考图按上传槽位在前、外部 URL 在后的顺序提交。每边至少 256 像素，超过 4 MP 的图片由 Atlas 按比例缩小。`auto` 沿用第一张图的比例。分辨率以此端点 Schema 的枚举为准。分辨率档位决定 Atlas 的单图价格，4K 可能需要数分钟。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/edit#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/edit",
  "prompt": "Use image 1 for the layout and give it warmer colors.",
  "reference_images": ["https://example.com/poster.png"],
  "aspect_ratio": "auto",
  "resolution": "1k",
  "enable_prompt_expansion": false,
  "output_format": "jpeg",
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、第一张参考图、画面比例、分辨率和图片格式。高级参数为其他参考图、外部 URL、内容审核容忍度及提示词扩写。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
