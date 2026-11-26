# 腾讯 Vega Video 1.0 Pro 参考生视频

结合起始图、参考图、视频或音频生成视频，可选智能时长。 Atlas Cloud 模型 ID 为 `tencent/vega-video-1.0-pro/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-video-1.0-pro/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                              | 必填         | 默认值                                          | 输入约定                                           |
| ------------------ | ----------------------------------------------------------- | ------------ | ----------------------------------------------- | -------------------------------------------------- |
| `model`            | `execution.config.model`                                    | 是           | `tencent/vega-video-1.0-pro/reference-to-video` | 工作机从执行配置读取                               |
| `prompt`           | `prompt`                                                    | 是           | 官方示例                                        | 最多 7,000 字符                                    |
| `image`            | `first_frame` 或 `first_frame_source`                       | 素材至少一项 | 省略                                            | 起始帧。上传、公开 URL 或 Base64                   |
| `reference_images` | `reference_image_1` 至 `reference_image_9`、`image_sources` | 素材至少一项 | 省略                                            | 参考图片。上传、公开 URL 或 Base64                 |
| `reference_videos` | `reference_video_1` 至 `reference_video_3`、`video_sources` | 素材至少一项 | 省略                                            | 参考视频。上传后转换为公开 URL，或直接填写公开 URL |
| `reference_audios` | `reference_audio_1` 至 `reference_audio_3`、`audio_sources` | 素材至少一项 | 省略                                            | 参考音频。上传后转换为公开 URL，或直接填写公开 URL |
| `duration`         | `duration`                                                  | 否           | 5                                               | 4 至 15 秒的整数，`-1` 为智能时长                  |
| `resolution`       | `resolution`                                                | 否           | `480P`                                          | `480P`、`720P`、`1080P`、`2K`、`4K`                |
| `aspect_ratio`     | `aspect_ratio`                                              | 否           | `16:9`                                          | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`adaptive`    |
| `generate_audio`   | `generate_audio`                                            | 否           | `true`                                          | 是否生成视频声音                                   |
| `storage_mode`     | `storage_mode`                                              | 否           | `Temporary`                                     | `Permanent` 或 `Temporary`，影响腾讯云点播侧保留   |
| `quality_mode`     | `quality_mode`                                              | 否           | 省略                                            | `Standard`、`Fast`、`SuperFast`，用于 720P 及以上  |
| `enhance_prompt`   | `enhance_prompt`                                            | 否           | `false`                                         | 是否在生成前扩写提示词                             |
| `moderation_mode`  | `moderation_mode`                                           | 否           | `Moderation_L1`                                 | `Moderation_L0`、`Moderation_L1`、`Moderation_L2`  |

图像上传使用 JPEG、PNG 或 WebP，图像来源可填写公开 URL、带媒体类型的 Base64 数据网址或纯 Base64。每组先按上传栏位排序，再追加逐行填写的来源。上传栏位的数量由 ComfyShop 表单提供，文本来源可继续追加，Atlas 检查上游素材数量限制。ComfyShop 每个图片来源字段限制为 4 MiB。

智能时长由模型决定成品长度。选择 480P 时，工作机省略 `quality_mode`。`storage_mode` 控制腾讯云点播中的源视频保留。Atlas 将两种存储模式的成品都复制到自己的存储，工作机再从成品地址下载。 [官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-video-1.0-pro-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-video-1.0-pro-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-video-1.0-pro-reference-to-video.md) · [Vega Video 1.0 系列](https://www.atlascloud.ai/models/wand-vega-video-1.0)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-video-1.0-pro/reference-to-video#usage-examples)

```json
{
  "model": "tencent/vega-video-1.0-pro/reference-to-video",
  "prompt": "参考图中的木屋亮起灯，镜头按参考视频的方向侧移，保留夜间背景声。",
  "reference_images": ["https://example.com/cabin.png"],
  "reference_videos": ["https://example.com/camera.mp4"],
  "reference_audios": ["https://example.com/night.mp3"],
  "duration": 5,
  "resolution": "480P",
  "aspect_ratio": "16:9",
  "generate_audio": true,
  "storage_mode": "Temporary",
  "enhance_prompt": false,
  "moderation_mode": "Moderation_L1"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、第一张参考图、提示词、时长、分辨率和画面比例位于默认区。其余素材、来源、生成音频、存储、质量模式、提示词增强及审核级别位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
