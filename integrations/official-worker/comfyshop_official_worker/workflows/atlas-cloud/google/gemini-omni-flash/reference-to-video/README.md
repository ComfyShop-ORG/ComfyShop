# Gemini Omni Flash 参考生视频

用人物、场景或风格参考图引导生成带音频的 720p 视频。 Atlas Cloud 模型 ID 为 `google/gemini-omni-flash/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                                                         | 必填 | 默认值                                        | 输入约定                                                                                           |
| ---------------- | ---------------------------------------------------------------------- | ---- | --------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `model`          | `execution.config.model`                                               | 是   | `google/gemini-omni-flash/reference-to-video` | 工作机从执行配置读取                                                                               |
| `prompt`         | `prompt`                                                               | 是   | 无                                            | 最多 20,000 字符                                                                                   |
| `images`         | `reference_image_1` 至 `reference_image_10`、`reference_image_sources` | 是   | 无                                            | 按请求 Schema 接受一至十张 PNG、JPEG 或 WebP，每张最多 20 MB。接受上传、公开网址或 Base64 数据网址 |
| `duration`       | `duration`                                                             | 否   | 10                                            | 3 至 10 秒的整数                                                                                   |
| `aspect_ratio`   | `aspect_ratio`                                                         | 否   | `16:9`                                        | `16:9` 或 `9:16`                                                                                   |
| `resolution`     | `resolution`                                                           | 否   | `720p`                                        | 固定为 `720p`                                                                                      |
| `thinking_level` | `thinking_level`                                                       | 否   | `default`                                     | `default`、`high` 或 `low`                                                                         |
| `seed`           | `seed`                                                                 | 否   | -1                                            | 整数。-1 由模型随机选取种子                                                                        |

工作机先排列上传图，再追加逐行填写的图片来源。该模型的请求 Schema 将 `images.maxItems` 设为 10，模型说明中列出的用量为一至五张。工作流采用 Schema 的字段与上限。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-flash-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-flash-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-flash-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video#usage-examples)

```json
{
  "model": "google/gemini-omni-flash/reference-to-video",
  "prompt": "让参考图里的陶瓷杯缓缓转动，镜头由近到远，伴随轻微风声。",
  "images": ["https://example.com/cup.webp"],
  "duration": 5,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "thinking_level": "default",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、时长和比例位于默认区。其余参考图、素材来源、推理程度和种子位于高级区。分辨率是隐藏参数。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
