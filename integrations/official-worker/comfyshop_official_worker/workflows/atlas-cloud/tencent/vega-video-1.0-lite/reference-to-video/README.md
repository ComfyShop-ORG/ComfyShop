# 腾讯 Vega Video 1.0 Lite 参考生视频

用起始图、参考图、参考视频或参考音频生成 4 至 15 秒的视频。 Atlas Cloud 模型 ID 为 `tencent/vega-video-1.0-lite/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-video-1.0-lite/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                              | 必填         | 默认值                                           | 输入约定                                                |
| ------------------ | ----------------------------------------------------------- | ------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `model`            | `execution.config.model`                                    | 是           | `tencent/vega-video-1.0-lite/reference-to-video` | 工作机从执行配置读取                                    |
| `prompt`           | `prompt`                                                    | 是           | 官方示例                                         | 最多 7,000 字符                                         |
| `image`            | `first_frame` 或 `first_frame_source`                       | 素材至少一项 | 省略                                             | 起始帧。上传、公开 URL 或 Base64                        |
| `reference_images` | `reference_image_1` 至 `reference_image_9`、`image_sources` | 素材至少一项 | 省略                                             | 参考图，与起始图合计最多 9 张。上传、公开 URL 或 Base64 |
| `reference_videos` | `reference_video_1` 至 `reference_video_3`、`video_sources` | 素材至少一项 | 省略                                             | 最多 3 段，上传后转换为公开 URL，或直接填写公开视频 URL |
| `reference_audios` | `reference_audio_1` 至 `reference_audio_3`、`audio_sources` | 素材至少一项 | 省略                                             | 最多 3 段，上传后转换为公开 URL，或直接填写公开音频 URL |
| `duration`         | `duration`                                                  | 否           | 5                                                | 4 至 15 秒的整数                                        |
| `resolution`       | `resolution`                                                | 否           | `480P`                                           | `480P`、`768P`、`1080P`、`2K`、`4K`                     |
| `aspect_ratio`     | `aspect_ratio`                                              | 否           | `16:9`                                           | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`adaptive`         |
| `generate_audio`   | `generate_audio`                                            | 否           | `true`                                           | 是否生成视频声音                                        |
| `storage_mode`     | `storage_mode`                                              | 否           | `Temporary`                                      | `Permanent` 或 `Temporary`，影响腾讯云点播侧保留        |
| `generate_mode`    | `generate_mode`                                             | 否           | `Standard`                                       | `Standard`、`Fast`、`StandardMovie`                     |
| `quality_mode`     | `quality_mode`                                              | 否           | `Standard`                                       | `Standard`、`Fast`、`SuperFast`                         |
| `enhance_prompt`   | `enhance_prompt`                                            | 否           | `false`                                          | 是否在生成前扩写提示词                                  |
| `moderation_mode`  | `moderation_mode`                                           | 否           | `Moderation_L1`                                  | `Moderation_L0`、`Moderation_L1`、`Moderation_L2`       |

图片、视频和音频合计最多 12 项。图片使用 JPEG、PNG 或 WebP，每张最多 30 MB。填写图片来源时支持带媒体类型的数据网址或纯 Base64，ComfyShop 每个图片来源字段限制为 4 MiB。各组先按上传栏位排序，再追加逐行填写的来源。接口适用非真人参考素材。

`storage_mode` 控制腾讯云点播中的源视频保留。Atlas 将两种存储模式的成品都复制到自己的存储，工作机再从成品地址下载。 [官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-video-1.0-lite-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-video-1.0-lite-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-video-1.0-lite-reference-to-video.md) · [Vega Video 1.0 系列](https://www.atlascloud.ai/models/wand-vega-video-1.0)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-video-1.0-lite/reference-to-video#usage-examples)

```json
{
  "model": "tencent/vega-video-1.0-lite/reference-to-video",
  "prompt": "让镜头沿着参考图里的滨海步道缓慢前行，配合参考音频中的海浪。",
  "reference_images": ["https://example.com/boardwalk.png"],
  "reference_videos": ["https://example.com/camera.mp4"],
  "reference_audios": ["https://example.com/surf.mp3"],
  "duration": 5,
  "resolution": "480P",
  "aspect_ratio": "16:9",
  "generate_audio": true,
  "storage_mode": "Temporary",
  "generate_mode": "Standard",
  "quality_mode": "Standard",
  "enhance_prompt": false,
  "moderation_mode": "Moderation_L1"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、第一张参考图、提示词、时长、分辨率和画面比例位于默认区。其余素材、来源、生成音频、存储、生成和质量模式、提示词增强及审核级别位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
