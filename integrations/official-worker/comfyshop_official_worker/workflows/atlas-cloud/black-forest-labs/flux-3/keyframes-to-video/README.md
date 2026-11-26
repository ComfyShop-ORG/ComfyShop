# FLUX 3 关键帧生视频

按帧号放置 1 至 10 张关键帧图片，生成 5 至 20 秒的视频。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/keyframes-to-video`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/keyframes-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                              | 必填 | 默认值                                        | 输入约定                                                   |
| ------------------ | --------------------------------------------------------------------------- | ---- | --------------------------------------------- | ---------------------------------------------------------- |
| `model`            | `execution.config.model`                                                    | 是   | `black-forest-labs/flux-3/keyframes-to-video` | 工作机从执行配置读取                                       |
| `keyframes`        | `keyframe_1_image` 至 `keyframe_10_image`，与同槽位的 `_url`、`_index` 配对 | 是   | 第一槽位帧号 `0`                              | 1 至 10 个对象，每个对象包含 `image_url` 和 `frame_index`  |
| `prompt`           | `prompt`                                                                    | 否   | —                                             | 描述画面、动作和声音，可留空                               |
| `aspect_ratio`     | `aspect_ratio`                                                              | 否   | `auto`                                        | `auto`、`21:9`、`2:1`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `resolution`       | `resolution`                                                                | 否   | `720p`                                        | `720p` 或 `1080p`                                          |
| `duration`         | `duration_seconds`                                                          | 否   | `5`                                           | 5 至 20 秒，整数                                           |
| `generate_audio`   | `generate_audio`                                                            | 否   | `true`                                        | 生成音频                                                   |
| `safety_tolerance` | `safety_tolerance`                                                          | 否   | `2`                                           | 整数 0 至 4，0 最严格                                      |
| `seed`             | `seed`                                                                      | 否   | —                                             | 非负整数，留空时省略                                       |

关键帧图片支持 PNG、JPEG 和 WebP。为每个使用的槽位上传一张图片或填写一个公开 URL，然后填写对应帧号。成品帧率为 24 fps，帧号从 0 至 `duration × 24`，各帧号须唯一。第一槽位默认帧号为 0，其他使用的槽位需要填写帧号。工作机在提交请求前校验这些约定。

静态 Schema 的提交路由记录为 `generateImage`。本工作流采用模型 API 页 cURL 示例中的 `generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/keyframes-to-video#usage-examples)

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-keyframes-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-keyframes-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-keyframes-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/keyframes-to-video#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/keyframes-to-video",
  "keyframes": [
    { "image_url": "https://example.com/starting-frame.png", "frame_index": 0 },
    { "image_url": "https://example.com/ending-frame.png", "frame_index": 120 }
  ],
  "prompt": "The lantern rises through the rain and fades into the mist.",
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "duration": 5,
  "generate_audio": true,
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、画面比例、分辨率、时长和首个关键帧槽位。高级参数为其他关键帧、外部 URL、内容审核容忍度、同步音频和种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
