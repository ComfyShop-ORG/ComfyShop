# FLUX 3 首尾帧生视频

在两张指定画面之间生成 5 至 20 秒的视频。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/first-last-frame-to-video`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/first-last-frame-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                        | 必填 | 默认值                                               | 输入约定                                                   |
| ------------------ | ------------------------------------- | ---- | ---------------------------------------------------- | ---------------------------------------------------------- |
| `model`            | `execution.config.model`              | 是   | `black-forest-labs/flux-3/first-last-frame-to-video` | 工作机从执行配置读取                                       |
| `start_image_url`  | `first_frame` 或 `first_frame_source` | 是   | —                                                    | JPEG、PNG 或 WebP 的上传或公开 URL，指定首帧               |
| `end_image_url`    | `last_frame` 或 `last_frame_source`   | 是   | —                                                    | JPEG、PNG 或 WebP 的上传或公开 URL，指定尾帧               |
| `prompt`           | `prompt`                              | 否   | —                                                    | 描述画面、动作和声音，可留空                               |
| `aspect_ratio`     | `aspect_ratio`                        | 否   | `auto`                                               | `auto`、`21:9`、`2:1`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `resolution`       | `resolution`                          | 否   | `720p`                                               | `720p` 或 `1080p`                                          |
| `duration`         | `duration_seconds`                    | 否   | `5`                                                  | 5 至 20 秒，整数，用于定位尾帧                             |
| `generate_audio`   | `generate_audio`                      | 否   | `true`                                               | 生成音频                                                   |
| `safety_tolerance` | `safety_tolerance`                    | 否   | `2`                                                  | 整数 0 至 4，0 最严格                                      |
| `seed`             | `seed`                                | 否   | —                                                    | 非负整数，留空时省略                                       |

静态 Schema 的提交路由记录为 `generateImage`。本工作流采用模型 API 页 cURL 示例中的 `generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/first-last-frame-to-video#usage-examples)

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-first-last-frame-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-first-last-frame-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-first-last-frame-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/first-last-frame-to-video#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/first-last-frame-to-video",
  "start_image_url": "https://example.com/start.png",
  "end_image_url": "https://example.com/end.png",
  "prompt": "The lantern sways gently as rain falls behind it.",
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "duration": 5,
  "generate_audio": true,
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为起始图、结束图、提示词、画面比例、分辨率和时长。高级参数为首尾帧 URL、内容审核容忍度、同步音频和种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
