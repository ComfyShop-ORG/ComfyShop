# Gemini Omni 1.2 Flash 参考生视频

用参考图或短片引导生成带同步音频的新视频。 Atlas Cloud 模型 ID 为 `google/gemini-omni-1.2-flash/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                         | 必填     | 默认值                                            | 输入约定                                                                          |
| ------------------ | ---------------------------------------------------------------------- | -------- | ------------------------------------------------- | --------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                               | 是       | `google/gemini-omni-1.2-flash/reference-to-video` | 工作机从执行配置读取                                                              |
| `prompt`           | `prompt`                                                               | 是       | 无                                                | 最多 20,000 字符                                                                  |
| `reference_images` | `reference_image_1` 至 `reference_image_10`、`reference_image_sources` | 条件必填 | 无                                                | 一至十张 PNG、JPEG 或 WebP，单张最多 20 MB。接受上传、公开 URL 或 Base64 数据网址 |
| `reference_videos` | `reference_video_1` 至 `reference_video_3`、`reference_video_sources`  | 条件必填 | 无                                                | 一至三段 MP4，每段最多 3 秒。接受上传或公开 URL。成片长 11 秒或更长时最多一段     |
| `duration`         | `duration`                                                             | 否       | 10                                                | 3 至 15 秒的整数。11 秒或更长时最多一段参考视频                                   |
| `aspect_ratio`     | `aspect_ratio`                                                         | 否       | `16:9`                                            | `16:9` 或 `9:16`                                                                  |
| `resolution`       | `resolution`                                                           | 否       | `720p`                                            | `360p`、`720p`、`1080p` 或 `4k`                                                   |
| `thinking_level`   | `thinking_level`                                                       | 否       | `default`                                         | `default`、`high` 或 `low`                                                        |
| `seed`             | `seed`                                                                 | 否       | -1                                                | 整数。-1 由模型随机选取种子                                                       |

两组参考素材至少提供一组，也可以同时提交。工作机先按槽位排列上传文件，再追加手工填写的地址。用自然语言描述参考素材，例如「按照第一段参考视频的镜头移动方式拍摄第一张图中的街道」。参考视频的音轨不参与生成。文本来源框最多容纳 4,194,304 个字符。模型同时生成画面和声音。360p 可用于预览，1080p 与 4K 由模型放大原生帧。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-1.2-flash-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-1.2-flash-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-1.2-flash-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/reference-to-video#usage-examples)

```json
{
  "model": "google/gemini-omni-1.2-flash/reference-to-video",
  "prompt": "在第一张参考图中的街道复现第一段参考视频的缓慢推进镜头，加入雨后街道的环境声。",
  "reference_images": ["https://example.com/street.webp"],
  "reference_videos": ["https://example.com/camera.mp4"],
  "duration": 12,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "thinking_level": "default",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一组图片和视频上传槽位、时长、比例和分辨率位于默认区。其余槽位、素材地址、推理程度和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
