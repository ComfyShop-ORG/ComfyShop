# VEED Lipsync 视频对口型

用新音频驱动原视频人物的口型，适合单人演讲和旁白视频。 Atlas Cloud 模型 ID 为 `veed/lipsync`。[官方模型 API](https://www.atlascloud.ai/models/veed/lipsync)

## Atlas 接口参数

| Atlas 参数  | ComfyShop 字段                    | 必填 | 默认值         | 输入约定                                                            |
| ----------- | --------------------------------- | ---- | -------------- | ------------------------------------------------------------------- |
| `model`     | `execution.config.model`          | 是   | `veed/lipsync` | 工作机从执行配置读取                                                |
| `video_url` | `source_video` 或 `video_source`  | 是   | —              | MP4、MOV 或 WebM，接受上传、公开 URL、Base64 数据 URI 或原始 Base64 |
| `audio_url` | `driving_audio` 或 `audio_source` | 是   | —              | WAV、MP3 或 M4A，接受上传、公开 URL、Base64 数据 URI 或原始 Base64  |

提供一段原视频和一段新音频。上传文件时，工作机把文件交给 Atlas 素材上传接口并传递返回的临时地址。

[官方 Schema](https://static.atlascloud.ai/model/schema/veed-lipsync.json) · [官方示例数据](https://static.atlascloud.ai/model/example/veed-lipsync.json) · [模型说明](https://static.atlascloud.ai/model/readme/veed-lipsync.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/veed/lipsync/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/veed/lipsync#usage-examples)

```json
{
  "model": "veed/lipsync",
  "video_url": "https://static.atlascloud.ai/media/videos/f6f00808c3272d50321545e31065bec9.mp4",
  "audio_url": "https://static.atlascloud.ai/media/audios/2ef9c9de8f673a1e4c96a455c4264eb9.mp3"
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括原视频和驱动音频。高级参数包括两个素材来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
