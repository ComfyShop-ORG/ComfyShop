# Grok Imagine Video 图生视频

从一张起始图和动作提示词生成 1 至 15 秒的视频。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-video/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-video/image-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                        | 必填 | 默认值                                  | 输入约定                                                       |
| -------------- | ------------------------------------- | ---- | --------------------------------------- | -------------------------------------------------------------- |
| `model`        | `execution.config.model`              | 是   | `xai/grok-imagine-video/image-to-video` | 工作机从执行配置读取                                           |
| `image_url`    | `first_frame` 或 `first_frame_source` | 是   | —                                       | JPEG、PNG 或 WebP，接受上传、公开 HTTPS URL 或 Base64 Data URI |
| `prompt`       | `prompt`                              | 是   | —                                       | 描述起始图的动作和镜头                                         |
| `duration`     | `duration_seconds`                    | 否   | `8`                                     | 整数 1 至 15 秒                                                |
| `resolution`   | `resolution`                          | 否   | `720p`                                  | `480p` 或 `720p`                                               |
| `aspect_ratio` | `aspect_ratio`                        | 否   | `16:9`                                  | `1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`              |

Schema 将 `aspect_ratio` 的默认值标为 `16:9`。选择「由接口决定」会省略该字段，接口说明此时匹配起始图比例。指定其他比例可能拉伸画面。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-video-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-video-image-to-video.json)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/xai/grok-imagine-video-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-video/image-to-video#usage-examples)

```json
{
  "model": "xai/grok-imagine-video/image-to-video",
  "image_url": "https://example.com/starting-frame.png",
  "prompt": "Move slowly toward the lighthouse as the waves rise.",
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为起始图、提示词、时长、分辨率和画面比例。高级参数为起始图的外部来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
