# FLUX 3 视频延长

从源视频的最后几帧继续生成 5 至 20 秒，可补充动作和声音描述。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/extend-video`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/extend-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                   | 必填 | 默认值                                  | 输入约定                                                   |
| ------------------ | -------------------------------- | ---- | --------------------------------------- | ---------------------------------------------------------- |
| `model`            | `execution.config.model`         | 是   | `black-forest-labs/flux-3/extend-video` | 工作机从执行配置读取                                       |
| `video_url`        | `source_video` 或 `video_source` | 是   | —                                       | 上传或公开 URL，MP4，短于 15 秒且小于 50 MB                |
| `prompt`           | `prompt`                         | 否   | —                                       | 描述最后一帧之后的动作、场景或声音                         |
| `aspect_ratio`     | `aspect_ratio`                   | 否   | `auto`                                  | `auto`、`21:9`、`2:1`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `resolution`       | `resolution`                     | 否   | `720p`                                  | `720p` 或 `1080p`                                          |
| `duration`         | `duration_seconds`               | 否   | `5`                                     | 增加 5 至 20 秒，整数                                      |
| `generate_audio`   | `generate_audio`                 | 否   | `true`                                  | 生成音频                                                   |
| `safety_tolerance` | `safety_tolerance`               | 否   | `2`                                     | 整数 0 至 4，0 最严格                                      |
| `seed`             | `seed`                           | 否   | —                                       | 非负整数，留空时省略                                       |

`duration` 控制续写片段长度。`auto` 比例保留源视频比例。工作机检查上传的 MP4 容器、大小与已知时长，外部 URL 由 Atlas 校验。

静态 Schema 的提交路由记录为 `generateImage`。本工作流采用模型 API 页 cURL 示例中的 `generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/extend-video#usage-examples)

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-extend-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-extend-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-extend-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/extend-video#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/extend-video",
  "video_url": "https://example.com/source.mp4",
  "prompt": "The camera follows the lantern until it vanishes into the mist.",
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "duration": 5,
  "generate_audio": true,
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为源视频、提示词、画面比例、分辨率和续写时长。高级参数为源视频 URL、内容审核容忍度、同步音频和种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
