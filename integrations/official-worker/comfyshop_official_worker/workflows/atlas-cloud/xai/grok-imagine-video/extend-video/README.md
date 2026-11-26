# Grok Imagine Video 视频续写

在一段 MP4 结尾追加 2 至 10 秒，输出原视频和续写片段。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-video/extend-video`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-video/extend-video)

## Atlas 接口参数

| Atlas 参数  | ComfyShop 字段                   | 必填 | 默认值                                | 输入约定                                  |
| ----------- | -------------------------------- | ---- | ------------------------------------- | ----------------------------------------- |
| `model`     | `execution.config.model`         | 是   | `xai/grok-imagine-video/extend-video` | 工作机从执行配置读取                      |
| `video_url` | `source_video` 或 `video_source` | 是   | —                                     | 2 至 15 秒的 MP4 上传或公开 URL，任选一种 |
| `prompt`    | `prompt`                         | 是   | —                                     | 描述最后一帧之后的动作或画面              |
| `duration`  | `duration_seconds`               | 否   | `6`                                   | 续写片段整数 2 至 10 秒                   |

源视频容器为 MP4，官方列举 H.264、H.265、AV1 等编码。成品包含原视频和续写片段，最高 720p。工作机会检查上传素材的容器和已知时长，外部 URL 由 Atlas 校验。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-video-extend-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-video-extend-video.json)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/xai/grok-imagine-video-extend-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-video/extend-video#usage-examples)

```json
{
  "model": "xai/grok-imagine-video/extend-video",
  "prompt": "Follow the boat as it leaves the harbor.",
  "video_url": "https://example.com/source.mp4",
  "duration": 6
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为源视频、续写提示词和续写时长。高级参数为源视频 URL。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
