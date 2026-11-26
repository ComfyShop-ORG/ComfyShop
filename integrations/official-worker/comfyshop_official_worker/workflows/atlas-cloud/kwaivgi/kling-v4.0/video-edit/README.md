# 可灵 4.0 视频编辑

用文字、图片、视频和主体参考编辑已有片段，支持原生 4K、超分和 10 位 HDR。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0/video-edit`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/video-edit)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                        | 必填 | 默认值                          | 输入约定                                                               |
| ------------------ | --------------------------------------------------------------------- | ---- | ------------------------------- | ---------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                              | 是   | `kwaivgi/kling-v4.0/video-edit` | 工作机从执行配置读取                                                   |
| `prompt`           | `prompt`                                                              | 是   | 官方示例                        | 英文最多 26,000 字符，非英文最多 11,000。用 `@video_1` 引用原视频      |
| `video`            | `source_video` 或 `video_source`                                      | 是   | 无                              | MP4 或 MOV，3 至 30 秒，每边 700 至 4,553 像素，最多 300 MB            |
| `reference_images` | `reference_image_1` 至 `reference_image_10`、`image_sources`          | 否   | 省略                            | 最多 10 张，可上传或使用公开 URL 或 Base64                             |
| `reference_videos` | `reference_video_1` 至 `reference_video_4`、`reference_video_sources` | 否   | 省略                            | 最多 4 条 MP4 或 MOV，文件要求同原视频。原视频与参考视频合计最多 30 秒 |
| `elements`         | `elements`                                                            | 否   | 省略                            | 最多 7 个主体，其中视频主体最多 3 个                                   |
| `voice_ids`        | `voice_ids`                                                           | 否   | 省略                            | 最多 3 个已有或预设音色 ID，每行一个                                   |
| `duration`         | `duration`                                                            | 否   | 5                               | 3 至 30 秒的整数。选择跟随原视频时省略该字段                           |
| `resolution`       | `resolution`                                                          | 否   | `1080p`                         | `720p`、`1080p`、`4k`、`1080p-esr`、`2k-esr`、`4k-esr`                 |
| `dynamic_range`    | `dynamic_range`                                                       | 否   | `sdr`                           | `sdr` 或 `hdr`。10 位 HDR 只用于原生 `1080p` 或 `4k`                   |

原视频编号 `@video_1`，参考视频从 `@video_2` 开始。所有图片、视频、主体和音色合计最多 15 项。工作机检查提示词总长度，Atlas 检查语言对应的上限。Base64 文本使用 ComfyShop 单字段 4 MiB 上限。表单初值为 Schema 中的 5 秒。选择跟随原视频后，Atlas 使用原视频的实际时长。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-video-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-video-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-video-edit.md)

## 主体结构

- 已有主体直接使用正 64 位整数 `element_id`。
- 新建主体填写 `element_name`（最多 20 字符）、`reference_type`，可填写 `element_description`（最多 100 字符）。
- 图片主体使用 `image_refer`，提供 `frontal_image` 和最多 3 个 `refer_images`。官方调用示例允许省略额外参考图，此时 Atlas 复用正面图片。人物或拟人图片主体可通过字符串 `element_voice_id` 绑定现有音色。
- 视频主体使用 `video_refer` 和 1 个 3 至 8 秒的 `refer_videos` URL，用于真人主体。音色可通过独立的 `voice_ids` 参数传入。

[可灵自定义音色](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/video-edit#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0/video-edit",
  "prompt": "将 @video_1 的冷色布光改为柔和的日落色，保留构图和运镜。",
  "video": "https://example.com/source.mp4",
  "resolution": "1080p",
  "dynamic_range": "hdr"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、编辑指令、时长、分辨率和动态范围位于默认区。参考素材、主体和音色位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
