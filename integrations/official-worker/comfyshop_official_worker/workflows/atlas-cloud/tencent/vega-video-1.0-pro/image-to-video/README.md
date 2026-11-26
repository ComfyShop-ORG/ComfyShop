# 腾讯 Vega Video 1.0 Pro 图生视频

用起始图和文字生成视频，可用结束图固定最后画面，也可选择智能时长。 Atlas Cloud 模型 ID 为 `tencent/vega-video-1.0-pro/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-video-1.0-pro/image-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                        | 必填 | 默认值                                      | 输入约定                                          |
| ----------------- | ------------------------------------- | ---- | ------------------------------------------- | ------------------------------------------------- |
| `model`           | `execution.config.model`              | 是   | `tencent/vega-video-1.0-pro/image-to-video` | 工作机从执行配置读取                              |
| `prompt`          | `prompt`                              | 是   | 官方示例                                    | 最多 7,000 字符                                   |
| `image`           | `first_frame` 或 `first_frame_source` | 是   | 无                                          | 起始图。上传、公开 URL 或 Base64                  |
| `last_image`      | `last_frame` 或 `last_frame_source`   | 否   | 省略                                        | 结束图。上传、公开 URL 或 Base64                  |
| `duration`        | `duration`                            | 否   | 5                                           | 4 至 15 秒的整数，`-1` 为智能时长                 |
| `resolution`      | `resolution`                          | 否   | `480P`                                      | `480P`、`720P`、`1080P`、`2K`、`4K`               |
| `aspect_ratio`    | `aspect_ratio`                        | 否   | `16:9`                                      | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`adaptive`   |
| `generate_audio`  | `generate_audio`                      | 否   | `true`                                      | 是否生成视频声音                                  |
| `storage_mode`    | `storage_mode`                        | 否   | `Temporary`                                 | `Permanent` 或 `Temporary`，影响腾讯云点播侧保留  |
| `quality_mode`    | `quality_mode`                        | 否   | 省略                                        | `Standard`、`Fast`、`SuperFast`，用于 720P 及以上 |
| `enhance_prompt`  | `enhance_prompt`                      | 否   | `false`                                     | 是否在生成前扩写提示词                            |
| `moderation_mode` | `moderation_mode`                     | 否   | `Moderation_L1`                             | `Moderation_L0`、`Moderation_L1`、`Moderation_L2` |

图片可上传 JPEG、PNG 或 WebP，也可填写公开 URL、带媒体类型的 Base64 数据网址或纯 Base64。ComfyShop 每个来源字段限制为 4 MiB。按该型号的官方用法，结束图须与起始图一起提供。

智能时长由模型决定成品长度。选择 480P 时，工作机省略 `quality_mode`。`storage_mode` 控制腾讯云点播中的源视频保留。Atlas 将两种存储模式的成品都复制到自己的存储，工作机再从成品地址下载。 [官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-video-1.0-pro-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-video-1.0-pro-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-video-1.0-pro-image-to-video.md) · [Vega Video 1.0 系列](https://www.atlascloud.ai/models/wand-vega-video-1.0)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-video-1.0-pro/image-to-video#usage-examples)

```json
{
  "model": "tencent/vega-video-1.0-pro/image-to-video",
  "prompt": "镜头沿着步道升高，最后俯视结束图中的海湾。",
  "image": "https://example.com/opening.png",
  "last_image": "https://example.com/ending.png",
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

起始图、结束图、提示词、时长、分辨率和画面比例位于默认区。两帧来源、生成音频、存储、质量模式、提示词增强及审核级别位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
