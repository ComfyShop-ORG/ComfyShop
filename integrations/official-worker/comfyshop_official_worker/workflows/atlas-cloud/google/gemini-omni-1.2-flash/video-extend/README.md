# Gemini Omni 1.2 Flash 视频续写

用提示词为已有片段续写 3 至 10 秒，可选参考图。 Atlas Cloud 模型 ID 为 `google/gemini-omni-1.2-flash/video-extend`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/video-extend)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                         | 必填 | 默认值                                      | 输入约定                                                                          |
| ------------------ | ---------------------------------------------------------------------- | ---- | ------------------------------------------- | --------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                               | 是   | `google/gemini-omni-1.2-flash/video-extend` | 工作机从执行配置读取                                                              |
| `prompt`           | `prompt`                                                               | 是   | 无                                          | 描述后续画面与动作，最多 20,000 字符                                              |
| `video`            | `video`、`video_source`                                                | 是   | 无                                          | 一段 MP4。上传视频或填写公开 URL                                                  |
| `reference_images` | `reference_image_1` 至 `reference_image_10`、`reference_image_sources` | 否   | 无                                          | 一至十张 PNG、JPEG 或 WebP，每张最多 20 MB。接受上传、公开 URL 或 Base64 数据网址 |
| `duration`         | `duration`                                                             | 否   | 10                                          | 在片尾追加 3 至 10 秒                                                             |
| `resolution`       | `resolution`                                                           | 否   | `720p`                                      | `360p`、`720p`、`1080p` 或 `4k`                                                   |
| `thinking_level`   | `thinking_level`                                                       | 否   | `default`                                   | `default`、`high` 或 `low`                                                        |
| `seed`             | `seed`                                                                 | 否   | -1                                          | 整数。-1 由模型随机选取种子                                                       |

工作机将上传视频转换成 Atlas 素材地址。模型使用原视频末尾最多 10 秒作为上下文，续写沿用原画面比例。若原片包含人物讲话，Atlas 限制在续写内容中追加对话。使用自然语言说明人物或参考图如何出现在片尾。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-1.2-flash-video-extend.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-1.2-flash-video-extend.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-1.2-flash-video-extend.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/video-extend#usage-examples)

```json
{
  "model": "google/gemini-omni-1.2-flash/video-extend",
  "prompt": "镜头继续沿展厅前行，慢慢转向第一张参考图中的窗户。",
  "video": "https://example.com/gallery.mp4",
  "reference_images": ["https://example.com/wall.webp"],
  "duration": 6,
  "resolution": "720p",
  "thinking_level": "default",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、原视频、第一张参考图上传、续写时长和分辨率位于默认区。其他参考图、素材来源、推理程度与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
