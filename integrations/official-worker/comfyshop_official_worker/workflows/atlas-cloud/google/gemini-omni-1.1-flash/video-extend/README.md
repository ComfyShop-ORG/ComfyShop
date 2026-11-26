# Gemini Omni 1.1 Flash 视频续写

用提示词为已有片段续写 3 至 10 秒，可选参考图。 Atlas Cloud 模型 ID 为 `google/gemini-omni-1.1-flash/video-extend`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-1.1-flash/video-extend)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                         | 必填 | 默认值                                      | 输入约定                                                                          |
| ------------------ | ---------------------------------------------------------------------- | ---- | ------------------------------------------- | --------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                               | 是   | `google/gemini-omni-1.1-flash/video-extend` | 工作机从执行配置读取                                                              |
| `prompt`           | `prompt`                                                               | 是   | 无                                          | 描述后续画面与动作，最多 20,000 字符                                              |
| `video`            | `video`、`video_source`                                                | 是   | 无                                          | 一段最长 10 秒的 MP4。上传视频或填写公开 URL                                      |
| `reference_images` | `reference_image_1` 至 `reference_image_10`、`reference_image_sources` | 否   | 无                                          | 一至十张 PNG、JPEG 或 WebP，每张最多 20 MB。接受上传、公开 URL 或 Base64 数据网址 |
| `duration`         | `duration`                                                             | 否   | 10                                          | 追加 3 至 10 秒。Atlas 要求成片总长不超过 40 秒                                   |
| `resolution`       | `resolution`                                                           | 否   | `720p`                                      | `360p`、`720p`、`1080p` 或 `4k`                                                   |
| `thinking_level`   | `thinking_level`                                                       | 否   | `default`                                   | `default`、`high` 或 `low`                                                        |
| `seed`             | `seed`                                                                 | 否   | -1                                          | 整数。-1 由模型随机选取种子                                                       |

工作机将上传视频转换成 Atlas 素材地址，并校验上传视频的时长。Atlas 检查公开 URL 的可访问性与媒体格式。供给该接口的原视频最长 10 秒，模型最多使用末尾 10 秒作为续写上下文。提示词中的 `<IMAGE_REF_0>` 指第一张参考图。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-1.1-flash-video-extend.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-1.1-flash-video-extend.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-1.1-flash-video-extend.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-1.1-flash/video-extend#usage-examples)

```json
{
  "model": "google/gemini-omni-1.1-flash/video-extend",
  "prompt": "镜头继续沿展厅前行，慢慢转向 <IMAGE_REF_0> 中的窗户。",
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
