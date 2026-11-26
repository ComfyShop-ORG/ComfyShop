# GPT Image 2.5 Flare 文生图

从提示词生成静态图片，支持尺寸预设、自定义宽高和透明背景。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2.5-flare/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2.5-flare/text-to-image)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                                     | 输入约定                                                                                                  |
| --------------- | ------------------------ | ---- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `openai/gpt-image-2.5-flare/text-to-image` | 工作机从执行配置读取                                                                                      |
| `prompt`        | `prompt`                 | 是   | 官方英文雨夜拉面摊示例                     | 最长 32000 字符                                                                                           |
| `quality`       | `quality`                | 否   | `medium`                                   | `auto`、`low`、`medium`、`high`、`xhigh`、`max`                                                           |
| `size`          | `size`、`custom_size`    | 否   | `1024x1024`                                | 支持 `auto`、预设或自定义 `宽x高`。每边 256 至 3840 且为 16 的倍数，总像素最多 8294400，宽高比 1:3 至 3:1 |
| `background`    | `background`             | 否   | `auto`                                     | `auto`、`opaque`、`transparent`。透明要求 PNG 或 WebP                                                     |
| `output_format` | `output_format`          | 否   | `png`                                      | `png`、`jpeg` 或 `webp`                                                                                   |
| `moderation`    | `moderation`             | 否   | `auto`                                     | `auto` 或 `low`                                                                                           |
| `n`             | `n`                      | 否   | 1                                          | 整数 1 至 10，指定生成数量                                                                                |

自定义宽高采用模型说明公布的范围。`moderation`、`quality: "auto"` 由请求 Schema 列出。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2.5-flare-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2.5-flare-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2.5-flare-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2.5-flare/text-to-image#usage-examples)

```json
{
  "model": "openai/gpt-image-2.5-flare/text-to-image",
  "prompt": "一张素描风格的城市骑行海报，突出黄色单车与纵向街景，顶部预留标题空间。",
  "size": "1024x1280",
  "quality": "low",
  "output_format": "png",
  "n": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，下载原件。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、质量、尺寸、输出格式和数量位于默认区。自定义宽高、背景与内容审核位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
