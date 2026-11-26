# Gemini Omni 1.1 Flash 图生视频

用起始图、提示词和可选的结束图生成带音频的视频。 Atlas Cloud 模型 ID 为 `google/gemini-omni-1.1-flash/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-1.1-flash/image-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                      | 必填 | 默认值                                        | 输入约定                                    |
| ---------------- | ----------------------------------- | ---- | --------------------------------------------- | ------------------------------------------- |
| `model`          | `execution.config.model`            | 是   | `google/gemini-omni-1.1-flash/image-to-video` | 工作机从执行配置读取                        |
| `prompt`         | `prompt`                            | 是   | 无                                            | 最多 20,000 字符                            |
| `image`          | `first_frame`、`first_frame_source` | 是   | 无                                            | 上传、公开图片 URL 或 Base64 数据网址三选一 |
| `last_image`     | `last_frame`、`last_frame_source`   | 否   | 无                                            | 可选结束帧，须同时提供起始图                |
| `duration`       | `duration`                          | 否   | 10                                            | 3 至 10 秒的整数                            |
| `aspect_ratio`   | `aspect_ratio`                      | 否   | `16:9`                                        | `16:9` 或 `9:16`                            |
| `resolution`     | `resolution`                        | 否   | `720p`                                        | `360p`、`720p`、`1080p` 或 `4k`             |
| `thinking_level` | `thinking_level`                    | 否   | `default`                                     | `default`、`high` 或 `low`                  |
| `seed`           | `seed`                              | 否   | -1                                            | 整数。-1 由模型随机选取种子                 |

两帧都接受 PNG、JPEG 或 WebP，单张最多 20 MB。文本输入框最多 4 MiB 字符，较大的素材通过上传或公开网址提供。模型同时生成画面和声音。360p 可用于预览，1080p 与 4K 由模型放大原生帧。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-1.1-flash-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-1.1-flash-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-1.1-flash-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-1.1-flash/image-to-video#usage-examples)

```json
{
  "model": "google/gemini-omni-1.1-flash/image-to-video",
  "prompt": "雨后的清晨，镜头沿石板路缓缓推进。街灯倒映在水坑里，远处有轻微的电车声。",
  "image": "https://example.com/opening.webp",
  "last_image": "https://example.com/closing.webp",
  "duration": 7,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "thinking_level": "default",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、两帧上传、时长、比例和分辨率位于默认区。素材地址、推理程度与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
