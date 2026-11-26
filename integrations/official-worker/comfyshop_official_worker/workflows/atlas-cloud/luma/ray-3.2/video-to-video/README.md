# Luma Ray 3.2 视频编辑

根据提示词编辑原视频，可选择保留原片或重新演绎的程度。 Atlas Cloud 模型 ID 为 `luma/ray-3.2/video-to-video`。[官方模型 API](https://www.atlascloud.ai/models/luma/ray-3.2/video-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                       | 必填 | 默认值                        | 输入约定                                                                                 |
| ------------ | ------------------------------------ | ---- | ----------------------------- | ---------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`             | 是   | `luma/ray-3.2/video-to-video` | 工作机从执行配置读取                                                                     |
| `video`      | `source_video` 或 `source_video_url` | 是   | —                             | 上传 MP4，或使用公开 HTTPS 的 MP4 地址                                                   |
| `prompt`     | `prompt`                             | 是   | Schema 提供可编辑示例         | 描述视频编辑需求                                                                         |
| `strength`   | `strength`                           | 否   | `flex_2`                      | `adhere_1`–`adhere_3` 保留，`flex_1`–`flex_3` 平衡，`reimagine_1`–`reimagine_3` 重新演绎 |
| `duration`   | `duration_seconds`                   | 否   | `5`                           | 整数 `5` 或 `10` 秒                                                                      |
| `resolution` | `resolution`                         | 否   | `720p`                        | `540p`、`720p` 或 `1080p`                                                                |
| `hdr`        | `hdr`                                | 否   | `false`                       | 仅用于 5 秒、720p 或 1080p，需要 HDR 权限                                                |

工作机在提交前校验 HDR、分辨率和时长。Atlas 样例数据含 `exr_export: false`，EXR 导出需要 Atlas 发布明确的请求与返回约定。[Luma 模型文档](https://docs.agents.lumalabs.ai/guides/model/)

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-ray-3.2-video-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-ray-3.2-video-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-ray-3.2-video-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/luma/ray-3.2/video-to-video#usage-examples)

```json
{
  "model": "luma/ray-3.2/video-to-video",
  "video": "https://example.com/source.mp4",
  "prompt": "将视频改为暖色调的复古胶片风格。",
  "strength": "flex_2",
  "duration": 5,
  "resolution": "720p",
  "hdr": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原视频、提示词、改动强度、时长和分辨率。高级参数为原视频 URL 与 HDR。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
