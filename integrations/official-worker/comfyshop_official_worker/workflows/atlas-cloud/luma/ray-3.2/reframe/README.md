# Luma Ray 3.2 视频重构画幅

把原视频重构为指定宽高比，可用提示词说明要保留的主体和位置。 Atlas Cloud 模型 ID 为 `luma/ray-3.2/reframe`。[官方模型 API](https://www.atlascloud.ai/models/luma/ray-3.2/reframe)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                       | 必填       | 默认值                 | 输入约定                                            |
| -------------- | ------------------------------------ | ---------- | ---------------------- | --------------------------------------------------- |
| `model`        | `execution.config.model`             | 是         | `luma/ray-3.2/reframe` | 工作机从执行配置读取                                |
| `video`        | `source_video` 或 `source_video_url` | 是         | —                      | 上传 MP4，或使用公开 HTTPS 的 MP4 地址              |
| `prompt`       | `prompt`                             | 请求须包含 | `""`                   | 可填写要保留的主体或位置。留空时发送空字符串        |
| `aspect_ratio` | `aspect_ratio`                       | 是         | `9:16`                 | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`21:9`、`9:21` |
| `resolution`   | `resolution`                         | 否         | `720p`                 | `540p`、`720p` 或 `1080p`                           |

成品为静音视频，Atlas 按输入视频时长计费。目标宽高比采用此 Atlas 端点 Schema 的枚举。官方调用示例允许 `prompt: ""`。

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-ray-3.2-reframe.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-ray-3.2-reframe.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-ray-3.2-reframe.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/luma/ray-3.2/reframe#usage-examples)

```json
{
  "model": "luma/ray-3.2/reframe",
  "video": "https://example.com/source.mp4",
  "prompt": "保持主体在画面中央。",
  "aspect_ratio": "9:16",
  "resolution": "720p"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原视频、提示词、目标宽高比和分辨率。高级参数为原视频 URL。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
