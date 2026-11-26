# PixVerse V6 首尾帧生成视频

根据首帧、尾帧和提示词生成 1 至 15 秒的过渡视频，可生成同步音频。 Atlas Cloud 模型 ID 为 `pixverse/v6/start-end-to-video`。[官方模型 API](https://www.atlascloud.ai/models/pixverse/v6/start-end-to-video)

## Atlas 接口参数

| Atlas 参数  | ComfyShop 字段                        | 必填 | 默认值                           | 输入约定                           |
| ----------- | ------------------------------------- | ---- | -------------------------------- | ---------------------------------- |
| `model`     | `execution.config.model`              | 是   | `pixverse/v6/start-end-to-video` | 工作机从执行配置读取               |
| `image`     | `first_frame` 或 `first_frame_source` | 是   | —                                | 首帧。上传、公开图片 URL 或 Base64 |
| `end_image` | `last_frame` 或 `last_frame_source`   | 是   | —                                | 尾帧。上传、公开图片 URL 或 Base64 |
| `prompt`    | `prompt`                              | 是   | —                                | 非空文字，1 至 5,000 字符          |
| `duration`  | `duration_seconds`                    | 否   | `5`                              | 整数 1 至 15 秒                    |
| `quality`   | `resolution`                          | 否   | `720p`                           | `360p`、`540p`、`720p`、`1080p`    |
| `sound`     | `generate_audio`                      | 否   | `true`                           | 生成同步音频                       |
| `seed`      | `seed`                                | 否   | 由 Atlas 选取                    | 整数，留空时省略参数               |

Atlas 模型说明要求同时提供提示词、首帧和尾帧。两帧接受 PNG、JPEG 或 WebP，每张不超过 10 MB。首帧宽高比除以尾帧宽高比须在 0.8 至 1.25 之间，Atlas 请求体不超过 20 MB。Base64 可用 Data URI 或原始字串。大素材可直接上传。工作机对两张已上传图片校验宽高比，外链图片由 Atlas 校验。

[官方 Schema](https://static.atlascloud.ai/model/schema/pixverse-v6-start-end-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/pixverse-v6-start-end-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/pixverse-v6-start-end-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/pixverse/v6-start-end-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/pixverse/v6/start-end-to-video#usage-examples)

```json
{
  "model": "pixverse/v6/start-end-to-video",
  "image": "https://example.com/first.png",
  "end_image": "https://example.com/last.png",
  "prompt": "日光渐亮，镜头缓缓移动到街角。",
  "duration": 5,
  "quality": "720p",
  "sound": true
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首帧、尾帧、提示词、时长和分辨率。高级参数为同步音频、随机种子和两帧的 URL 或 Base64 来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
