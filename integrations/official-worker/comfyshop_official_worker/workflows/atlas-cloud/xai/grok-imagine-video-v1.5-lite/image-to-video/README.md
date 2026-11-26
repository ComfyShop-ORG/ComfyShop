# Grok Imagine Video v1.5 Lite 图生视频

从一张起始图和动作提示词生成 1 至 15 秒的视频。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-video-v1.5-lite/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5-lite/image-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                        | 必填 | 默认值                                            | 输入约定                                                                 |
| ---------------- | ------------------------------------- | ---- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| `model`          | `execution.config.model`              | 是   | `xai/grok-imagine-video-v1.5-lite/image-to-video` | 工作机从执行配置读取                                                     |
| `image`          | `first_frame` 或 `first_frame_source` | 是   | —                                                 | JPEG、PNG 或 WebP，接受上传、公开图片 URL 或 Base64                      |
| `prompt`         | `prompt`                              | 是   | 官方可编辑示例                                    | 描述起始图的动作和镜头                                                   |
| `duration`       | `duration_seconds`                    | 否   | `8`                                               | 整数 1 至 15 秒                                                          |
| `resolution`     | `resolution`                          | 否   | `720p`                                            | `480p`、`720p`、`1080p`                                                  |
| `aspect_ratio`   | `aspect_ratio`                        | 否   | `auto`                                            | `auto`、`16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`3:2`、`2:3`、`21:9`、`5:2` |
| `generate_audio` | `generate_audio`                      | 否   | `true`                                            | 生成同步音频，关闭后为静音视频                                           |

`auto` 保留起始图比例。指定其他比例会拉伸画面。`1080p` 由 `720p` 放大。Atlas 按所选分辨率和成品秒数计费。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-video-v1.5-lite-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-video-v1.5-lite-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/xai-grok-imagine-video-v1.5-lite-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5-lite/image-to-video#usage-examples)

```json
{
  "model": "xai/grok-imagine-video-v1.5-lite/image-to-video",
  "image": "https://example.com/starting-frame.png",
  "prompt": "The girl slowly turns toward the camera and smiles as wind moves through her hair, soft cinematic lighting.",
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "auto",
  "generate_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为起始图、提示词、时长、分辨率和画面比例。高级参数为起始图的外部来源和同步音频。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
