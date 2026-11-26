# Sync Lipsync v3 视频对口型

用新音频重做原视频的口型，可选择音视频时长不同时的处理方式。 Atlas Cloud 模型 ID 为 `sync/lipsync-v3`。[官方模型 API](https://www.atlascloud.ai/models/sync/lipsync-v3)

## Atlas 接口参数

| Atlas 参数  | ComfyShop 字段                    | 必填 | 默认值            | 输入约定                                                                                           |
| ----------- | --------------------------------- | ---- | ----------------- | -------------------------------------------------------------------------------------------------- |
| `model`     | `execution.config.model`          | 是   | `sync/lipsync-v3` | 工作机从执行配置读取                                                                               |
| `video_url` | `source_video` 或 `video_source`  | 是   | —                 | MP4、MOV 或 WebM，接受上传、公开 URL、Base64 数据 URI 或原始 Base64                                |
| `audio_url` | `driving_audio` 或 `audio_source` | 是   | —                 | WAV、MP3 或 M4A，接受上传、公开 URL、Base64 数据 URI 或原始 Base64                                 |
| `sync_mode` | `sync_mode`                       | 是   | `cut_off`         | `cut_off` 裁剪到较短时长，`loop` 循环视频，`bounce` 来回播放，`silence` 补静音，`remap` 重映射时间 |

模型请求 Schema 将 `sync_mode` 列为必填并给出默认 `cut_off`，工作机每次传递当前选择。长素材可用上传或公开地址。

[官方 Schema](https://static.atlascloud.ai/model/schema/sync-lipsync-v3.json) · [官方示例数据](https://static.atlascloud.ai/model/example/sync-lipsync-v3.json) · [模型说明](https://static.atlascloud.ai/model/readme/sync-lipsync-v3.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/sync/lipsync-v3/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/sync/lipsync-v3#usage-examples)

```json
{
  "model": "sync/lipsync-v3",
  "video_url": "https://static.atlascloud.ai/media/videos/5b19ce5cf94cb3d1dcb93d0853642cf4.mp4",
  "audio_url": "https://static.atlascloud.ai/media/audios/09ea50e47cca25ede27a69c7cb67e38e.mp3",
  "sync_mode": "cut_off"
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括原视频、驱动音频和时长对齐方式。高级参数包括两个素材来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
