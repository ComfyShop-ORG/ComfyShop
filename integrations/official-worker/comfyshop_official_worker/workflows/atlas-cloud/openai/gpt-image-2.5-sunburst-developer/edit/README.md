# GPT Image 2.5 Sunburst Developer 图像编辑

使用 Developer 接口按提示词编辑最多 16 张参考图。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2.5-sunburst-developer/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2.5-sunburst-developer/edit)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                       | 必填 | 默认值                                         | 输入约定                                                                                             |
| --------------- | ---------------------------------------------------- | ---- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`                             | 是   | `openai/gpt-image-2.5-sunburst-developer/edit` | 工作机从执行配置读取                                                                                 |
| `prompt`        | `prompt`                                             | 是   | 官方英文礼篮示例                               | 最长 32000 字符                                                                                      |
| `images`        | `reference_1` 至 `reference_16`、`reference_sources` | 是   | 无                                             | 1 至 16 个公开 URL、Base64 data URL 或 Atlas `asset://ID` 引用                                       |
| `size`          | `size`、`custom_size`                                | 否   | `1024x1024`                                    | `auto`、预设或自定义 `宽x高`。每边 256 至 3840 且为 16 的倍数，总像素最多 8294400，宽高比 1:3 至 3:1 |
| `background`    | `background`                                         | 否   | `auto`                                         | `auto`、`opaque`、`transparent`。透明要求 PNG 或 WebP                                                |
| `output_format` | `output_format`                                      | 否   | `png`                                          | `png`、`jpeg` 或 `webp`                                                                              |
| `moderation`    | `moderation`                                         | 否   | `auto`                                         | `auto` 或 `low`                                                                                      |
| `n`             | `n`                                                  | 否   | 1                                              | 整数 1 至 10                                                                                         |

工作机按编号发送上传图，再按行追加文本来源。文本字段上限为 4 MiB，支持公开 URL、Base64 data URL 或有权使用的 `asset://ID`。静态示例含 `quality`，本接口的请求 Schema 和模型调用参数表采用上表字段。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2.5-sunburst-developer-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2.5-sunburst-developer-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2.5-sunburst-developer-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址替换为实际素材。[官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2.5-sunburst-developer/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-2.5-sunburst-developer/edit",
  "prompt": "为参考图中的绿色玻璃瓶换成淡粉色背景，保留瓶身反光和原有商标。",
  "images": ["https://example.com/glass-bottle.jpg"],
  "size": "1536x1024",
  "output_format": "png",
  "n": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，下载原件。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、尺寸、格式与数量位于默认区。其余参考图、素材地址及输出细节位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
