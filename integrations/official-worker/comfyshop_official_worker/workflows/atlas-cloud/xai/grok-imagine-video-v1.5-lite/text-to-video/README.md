# Grok Imagine Video v1.5 Lite 文生视频

用文字生成 1 至 15 秒的视频，可选择是否生成同步音频。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-video-v1.5-lite/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5-lite/text-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段           | 必填 | 默认值                                           | 输入约定                                                         |
| ---------------- | ------------------------ | ---- | ------------------------------------------------ | ---------------------------------------------------------------- |
| `model`          | `execution.config.model` | 是   | `xai/grok-imagine-video-v1.5-lite/text-to-video` | 工作机从执行配置读取                                             |
| `prompt`         | `prompt`                 | 是   | 官方可编辑示例                                   | 描述画面、动作、镜头和希望听到的声音                             |
| `duration`       | `duration_seconds`       | 否   | `8`                                              | 整数 1 至 15 秒                                                  |
| `resolution`     | `resolution`             | 否   | `720p`                                           | `480p`、`720p` 或 `1080p`                                        |
| `aspect_ratio`   | `aspect_ratio`           | 否   | `16:9`                                           | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`3:2`、`2:3`、`21:9`、`5:2` |
| `generate_audio` | `generate_audio`         | 否   | `true`                                           | 生成同步音频，关闭后为静音视频                                   |

`1080p` 由 `720p` 放大。Atlas 按所选分辨率和成品秒数计费。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-video-v1.5-lite-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-video-v1.5-lite-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/xai-grok-imagine-video-v1.5-lite-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5-lite/text-to-video#usage-examples)

```json
{
  "model": "xai/grok-imagine-video-v1.5-lite/text-to-video",
  "prompt": "A paper boat drifts down a rain-soaked street at dusk, neon reflections rippling on the water, soft rain ambience.",
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "generate_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、分辨率和画面比例。高级参数为同步音频。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
