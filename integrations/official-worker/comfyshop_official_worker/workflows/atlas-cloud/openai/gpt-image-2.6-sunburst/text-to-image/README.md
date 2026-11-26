# GPT Image 2.6 Sunburst 文生图

用文本生成静态图、GIF 动画或可编辑 SVG。工作机使用 Atlas Cloud 的图像接口。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2.6-sunburst/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2.6-sunburst/text-to-image)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段           | 必填 | 默认值                                        | 输入约定                                                                                                             |
| ------------------- | ------------------------ | ---- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `model`             | `execution.config.model` | 是   | `openai/gpt-image-2.6-sunburst/text-to-image` | 工作机从执行配置读取                                                                                                 |
| `prompt`            | `prompt`                 | 是   | 官方英文海獭示例                              | 最多 32000 字符。GIF 可描述动作和循环                                                                                |
| `quality`           | `quality`                | 否   | `medium`                                      | `auto`、`low`、`medium`、`high`、`xhigh`、`max`                                                                      |
| `complexity`        | `complexity`             | 否   | `high`                                        | `low`、`medium` 或 `high`。控制渲染前的规划深度                                                                      |
| `size`              | `size`、`custom_size`    | 否   | 静态 `1024x1024`，GIF `auto`                  | 支持 Schema 预设与模型说明中的自定义 `宽x高`。每边 256 至 3840 且为 16 的倍数，总像素最多 8294400，宽高比 1:3 至 3:1 |
| `background`        | `background`             | 否   | `auto`                                        | `auto`、`opaque`、`transparent`。透明要求 PNG、WebP 或 SVG                                                           |
| `output_format`     | `output_format`          | 否   | `png`                                         | `png`、`jpeg`、`webp`、`gif` 或 `svg`                                                                                |
| `frame_count`       | `frame_count`            | 否   | 9                                             | 仅 GIF，整数 2 至 64                                                                                                 |
| `frame_duration_ms` | `frame_duration_ms`      | 否   | 200                                           | 仅 GIF，整数 20 至 2000 毫秒，Atlas 按 10 毫秒取整                                                                   |
| `svg_model`         | `svg_model`              | 否   | `gpt-5.4-mini`                                | 仅 SVG，支持 `gpt-6-astra`、`gpt-6-luna`、`gpt-6.1-terra`、`gpt-6-sol`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini`         |
| `moderation`        | `moderation`             | 否   | `auto`                                        | `auto` 或 `low`                                                                                                      |
| `n`                 | `n`                      | 否   | 1                                             | 整数 1 至 10，SVG 必须为 1                                                                                           |

选择由接口决定尺寸时，工作机省略 `size`，以便 Atlas 使用对应格式的默认值。GIF 的尺寸指单帧，多帧拼成的图纸还受 Atlas 的总尺寸限制。SVG 的生成模型和自定义宽高来自官方模型说明，透明格式组合按 Schema 校验。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2.6-sunburst-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2.6-sunburst-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2.6-sunburst-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。以下示例请求八帧循环 GIF。SVG 则使用 `output_format: "svg"` 和 `n: 1`，可选 `svg_model`。[官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2.6-sunburst/text-to-image#usage-examples)

```json
{
  "model": "openai/gpt-image-2.6-sunburst/text-to-image",
  "prompt": "一只纸折燕子绕过弧线后回到原位，单色背景，动画首尾平滑衔接。",
  "output_format": "gif",
  "size": "512x512",
  "quality": "medium",
  "frame_count": 8,
  "frame_duration_ms": 120,
  "n": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，其中 SVG 以原件形式保存。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、质量、尺寸、格式和数量位于默认区。细节规划、自定义尺寸、背景、审核及格式专属参数位于高级区。成品以原格式保存。SVG 通过文本预览查看源码，可下载 `.svg` 原件。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
