# FLUX 3 视频编辑

按文字指示重新渲染 MP4，保留原视频的动作、长度和分辨率。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-3/edit-video`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-3/edit-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                   | 必填 | 默认值                                | 输入约定                                                  |
| ------------------ | -------------------------------- | ---- | ------------------------------------- | --------------------------------------------------------- |
| `model`            | `execution.config.model`         | 是   | `black-forest-labs/flux-3/edit-video` | 工作机从执行配置读取                                      |
| `video_url`        | `source_video` 或 `video_source` | 是   | —                                     | 上传 MP4 或填写公开 URL，任选一种。短于 15 秒，小于 50 MB |
| `prompt`           | `prompt`                         | 是   | —                                     | 描述要修改的画面内容                                      |
| `safety_tolerance` | `safety_tolerance`               | 否   | `2`                                   | 整数 0 至 4，0 最严格                                     |

成品保持原片的动作、时长、构图和分辨率。工作机会检查上传文件的容器、大小和已知时长。外部 URL 由 Atlas 校验。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-3-edit-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-3-edit-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-3-edit-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-3/edit-video#usage-examples)

```json
{
  "model": "black-forest-labs/flux-3/edit-video",
  "prompt": "Change the street lighting to a cool winter tone.",
  "video_url": "https://example.com/source.mp4",
  "safety_tolerance": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为源视频和编辑指令。高级参数为源视频 URL 和内容审核容忍度。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
