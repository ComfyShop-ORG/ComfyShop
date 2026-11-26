# Gemini Omni Flash 图生视频

用起始图和提示词生成带音频的 720p 视频。 Atlas Cloud 模型 ID 为 `google/gemini-omni-flash/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-flash/image-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                      | 必填 | 默认值                                    | 输入约定                                    |
| ---------------- | ----------------------------------- | ---- | ----------------------------------------- | ------------------------------------------- |
| `model`          | `execution.config.model`            | 是   | `google/gemini-omni-flash/image-to-video` | 工作机从执行配置读取                        |
| `prompt`         | `prompt`                            | 是   | 无                                        | 最多 20,000 字符                            |
| `image`          | `first_frame`、`first_frame_source` | 是   | 无                                        | 上传、公开图片 URL 或 Base64 数据网址三选一 |
| `duration`       | `duration`                          | 否   | 10                                        | 3 至 10 秒的整数                            |
| `aspect_ratio`   | `aspect_ratio`                      | 否   | `16:9`                                    | `16:9` 或 `9:16`                            |
| `resolution`     | `resolution`                        | 否   | `720p`                                    | 固定为 `720p`                               |
| `thinking_level` | `thinking_level`                    | 否   | `default`                                 | `default`、`high` 或 `low`                  |
| `seed`           | `seed`                              | 否   | -1                                        | 整数。-1 由模型随机选取种子                 |

起始图接受 PNG、JPEG 或 WebP，最多 20 MB。文本来源框最多容纳 4,194,304 个字符，较大的素材通过上传或公开网址提供。模型同时生成画面和声音。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-flash-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-flash-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-flash-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-flash/image-to-video#usage-examples)

```json
{
  "model": "google/gemini-omni-flash/image-to-video",
  "prompt": "雨后的清晨，镜头沿石板路缓缓推进。街灯倒映在水坑里，远处有轻微的电车声。",
  "image": "https://example.com/opening.webp",
  "duration": 7,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "thinking_level": "default",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、起始帧、时长和比例位于默认区。素材来源、推理程度与种子位于高级区。工作机提交固定的分辨率参数 `resolution=720p`。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
