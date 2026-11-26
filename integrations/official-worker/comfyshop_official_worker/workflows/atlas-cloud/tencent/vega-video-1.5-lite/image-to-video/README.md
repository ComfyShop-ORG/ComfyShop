# 腾讯 Vega Video 1.5 Lite 图生视频

用文字和起始图或结束图生成 2 至 30 秒的视频。 Atlas Cloud 模型 ID 为 `tencent/vega-video-1.5-lite/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-video-1.5-lite/image-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                        | 必填         | 默认值                                       | 输入约定                                          |
| ----------------- | ------------------------------------- | ------------ | -------------------------------------------- | ------------------------------------------------- |
| `model`           | `execution.config.model`              | 是           | `tencent/vega-video-1.5-lite/image-to-video` | 工作机从执行配置读取                              |
| `prompt`          | `prompt`                              | 是           | 官方示例                                     | 最多 7,000 字符                                   |
| `image`           | `first_frame` 或 `first_frame_source` | 两帧至少一项 | 省略                                         | 起始帧。上传、公开 URL 或 Base64                  |
| `last_image`      | `last_frame` 或 `last_frame_source`   | 两帧至少一项 | 省略                                         | 结束帧。上传、公开 URL 或 Base64                  |
| `duration`        | `duration`                            | 否           | 5                                            | 2 至 30 秒的整数，`-1` 为智能时长                 |
| `resolution`      | `resolution`                          | 否           | `480P`                                       | `480P`、`720P`、`1080P`、`2K`、`4K`               |
| `aspect_ratio`    | `aspect_ratio`                        | 否           | `16:9`                                       | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`adaptive`   |
| `generate_audio`  | `generate_audio`                      | 否           | `true`                                       | 是否生成视频声音                                  |
| `storage_mode`    | `storage_mode`                        | 否           | `Temporary`                                  | `Permanent` 或 `Temporary`，影响腾讯云点播侧保留  |
| `enhance_prompt`  | `enhance_prompt`                      | 否           | `false`                                      | 是否在生成前扩写提示词                            |
| `moderation_mode` | `moderation_mode`                     | 否           | `Moderation_L1`                              | `Moderation_L0`、`Moderation_L1`、`Moderation_L2` |

可上传 JPEG、PNG 或 WebP，每张最多 20 MB。来源可填写公开 URL、带媒体类型的 Base64 数据网址或纯 Base64。ComfyShop 每个来源字段限制为 4 MiB。Atlas 请求 Schema 将两帧定义为至少一项，模型用法示例从起始帧开始，腾讯云点播原生 API 要求起始帧。[腾讯云点播 API](https://cloud.tencent.com/document/product/266/126239)

智能时长由模型决定成品长度。静态示例还列有 `register_material`，工作流请求字段依据当前 Schema。`storage_mode` 控制腾讯云点播中的源视频保留。Atlas 将两种存储模式的成品都复制到自己的存储，工作机再从成品地址下载。 [官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-video-1.5-lite-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-video-1.5-lite-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-video-1.5-lite-image-to-video.md) · [Vega Video 1.5 系列](https://www.atlascloud.ai/models/wand-vega-video-1.5)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-video-1.5-lite/image-to-video#usage-examples)

```json
{
  "model": "tencent/vega-video-1.5-lite/image-to-video",
  "prompt": "从起始图的石拱门前推进，镜头停在结束图的广场中央。",
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

起始图、结束图、提示词、时长、分辨率和画面比例位于默认区。两帧来源、生成音频、存储、提示词增强及审核级别位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
