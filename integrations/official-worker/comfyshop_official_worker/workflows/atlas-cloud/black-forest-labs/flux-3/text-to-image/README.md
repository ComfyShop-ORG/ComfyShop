# FLUX 3 文生图

按提示词生成图片，可选择自动画面比例和最高 4K 的分辨率。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/text-to-image)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段            | 必填 | 默认值                                   | 输入约定                                                                                                    |
| ------------------------- | ------------------------- | ---- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`  | 是   | `black-forest-labs/flux-3/text-to-image` | 工作机从执行配置读取                                                                                        |
| `prompt`                  | `prompt`                  | 是   | —                                        | 自然语言提示词，可将需写入画面的文字放进引号                                                                |
| `aspect_ratio`            | `aspect_ratio`            | 否   | `auto`                                   | `auto`、`21:9`、`2:1`、`16:9`、`3:2`、`7:5`、`4:3`、`5:4`、`1:1`、`4:5`、`3:4`、`5:7`、`2:3`、`9:16`、`1:2` |
| `resolution`              | `resolution`              | 否   | `1k`                                     | `768sq`、`1k`、`2k`、`4k`                                                                                   |
| `enable_prompt_expansion` | `enable_prompt_expansion` | 否   | `false`                                  | 将短提示词扩写为更完整的描述                                                                                |
| `output_format`           | `output_format`           | 否   | `jpeg`                                   | `jpeg` 或 `png`                                                                                             |
| `safety_tolerance`        | `safety_tolerance`        | 否   | `2`                                      | 整数 0 至 4，0 最严格                                                                                       |

分辨率以此端点 Schema 的枚举为准。分辨率档位决定 Atlas 的单图价格，4K 可能需要数分钟。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/text-to-image#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/text-to-image",
  "prompt": "A hand-painted festival poster with the title \"Night Market\".",
  "aspect_ratio": "auto",
  "resolution": "1k",
  "enable_prompt_expansion": false,
  "output_format": "jpeg",
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、画面比例、分辨率和图片格式。高级参数为内容审核容忍度及提示词扩写。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
