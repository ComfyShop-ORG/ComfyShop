# Bach 1.0 Pro 文生视频

根据提示词生成 5 至 16 秒的视频，可保留自动生成的音轨。 Atlas Cloud 模型 ID 为 `video-rebirth/bach-1.0-pro/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/text-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段           | 必填 | 默认值                                     | 输入约定                                    |
| ---------------- | ------------------------ | ---- | ------------------------------------------ | ------------------------------------------- |
| `model`          | `execution.config.model` | 是   | `video-rebirth/bach-1.0-pro/text-to-video` | 工作机从执行配置读取                        |
| `prompt`         | `prompt`                 | 是   | `A cinematic daytime street scene.`        | 最多 6,500 字符                             |
| `duration`       | `duration`               | 否   | `5`                                        | 5 至 16 秒的整数                            |
| `resolution`     | `resolution`             | 否   | `1080p`                                    | `1080p` 或 `4k`                             |
| `aspect_ratio`   | `aspect_ratio`           | 否   | `16:9`                                     | `16:9`、`9:16`、`4:3`、`3:4`、`21:9`、`1:1` |
| `generate_audio` | `generate_audio`         | 否   | `true`                                     | 关闭后输出静音视频                          |
| `seed`           | `seed`                   | 否   | 随机                                       | 1 至 100,000 的整数                         |

[官方 Schema](https://static.atlascloud.ai/model/schema/video-rebirth-bach-1.0-pro-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/video-rebirth-bach-1.0-pro-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/video-rebirth-bach-1.0-pro-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/text-to-video#usage-examples)

```json
{
  "model": "video-rebirth/bach-1.0-pro/text-to-video",
  "prompt": "A cinematic daytime street scene.",
  "duration": 5,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "generate_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词、时长、分辨率和宽高比。高级参数包括音频与随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
