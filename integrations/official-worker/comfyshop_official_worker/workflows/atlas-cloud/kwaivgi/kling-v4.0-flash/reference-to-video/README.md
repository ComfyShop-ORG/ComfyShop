# 可灵 4.0 Flash 参考生视频

混合图片、视频、主体和音色生成 720p 视频，可加入一张起始关键帧。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0-flash/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                        | 必填     | 默认值                                        | 输入约定                                                                                      |
| ------------------ | --------------------------------------------------------------------- | -------- | --------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                              | 是       | `kwaivgi/kling-v4.0-flash/reference-to-video` | 工作机从执行配置读取                                                                          |
| `prompt`           | `prompt`                                                              | 是       | 官方示例                                      | 英文最多 26,000 字符，非英文最多 11,000。可以在提示词中引用素材                               |
| `image`            | `first_frame` 或 `first_frame_source`                                 | 否       | 省略                                          | 起始关键帧，支持上传、公开 URL 或 Base64                                                      |
| `reference_images` | `reference_image_1` 至 `reference_image_10`、`image_sources`          | 否       | 省略                                          | 参考图和起始关键帧合计最多 10 张                                                              |
| `reference_videos` | `reference_video_1` 至 `reference_video_5`、`reference_video_sources` | 条件必填 | 省略                                          | 最多 5 条。MP4 或 MOV，每条 3 至 20 秒、每边 700 至 4,553 像素、最多 300 MB。总时长最多 20 秒 |
| `elements`         | `elements`                                                            | 否       | 省略                                          | 最多 7 个主体，视频主体最多 3 个                                                              |
| `voice_ids`        | `voice_ids`                                                           | 否       | 省略                                          | 最多 3 个音色 ID，每行一个                                                                    |
| `duration`         | `duration`                                                            | 否       | 10                                            | 3 至 20 秒的整数                                                                              |
| `aspect_ratio`     | `aspect_ratio`                                                        | 否       | `auto`                                        | `auto`、`16:9`、`9:16`、`1:1`、`21:9`                                                         |
| `resolution`       | `resolution`                                                          | 否       | `720p`                                        | 固定 `720p`                                                                                   |
| `audio_mode`       | `audio_mode`                                                          | 否       | `native`                                      | `native` 生成同期声。`original` 保留第一条参考视频的音轨，需要至少一条参考视频                |

工作机检查提示词总长度，Atlas 检查语言对应的长度上限。起始图先于其他参考图编号，视频、主体和音色各按其数组顺序编号。所有参考素材合计最多 15 项。Base64 来源使用 ComfyShop 单字段 4 MiB 上限。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-flash-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-flash-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-flash-reference-to-video.md)

## 主体结构

- 已有主体直接使用正 64 位整数 `element_id`。
- 新建主体填写 `element_name`（最多 20 字符）、`reference_type`，可填写 `element_description`（最多 100 字符）。
- 图片主体使用 `image_refer`，提供 `frontal_image` 和最多 3 个 `refer_images`。官方调用示例允许省略额外参考图，此时 Atlas 复用正面图片。人物或拟人图片主体可通过字符串 `element_voice_id` 绑定现有音色。
- 视频主体使用 `video_refer` 和 1 个 3 至 8 秒的 `refer_videos` URL，用于真人主体。音色可通过独立的 `voice_ids` 参数传入。

[可灵自定义音色](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/reference-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0-flash/reference-to-video",
  "prompt": "保持 @image_1 中陶瓷杯的釉色，让镜头借鉴 @video_1 的缓慢推进节奏。",
  "image": "https://example.com/opening.png",
  "reference_videos": ["https://example.com/motion.mp4"],
  "duration": 10,
  "aspect_ratio": "auto",
  "resolution": "720p",
  "audio_mode": "original"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、起始关键帧、画面比例和时长位于默认区。参考素材、主体、音色和音频模式位于高级区。固定分辨率由工作机提交。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
