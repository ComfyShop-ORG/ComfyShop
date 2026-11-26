# Midjourney V8.1 图生视频

把一张首帧图片生成 4 段 5 秒视频，保留原图宽高比。 Atlas Cloud 模型 ID 为 `midjourney/v8.1/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/midjourney/v8.1/image-to-video)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                        | 必填 | 默认值                           | 输入约定                                   |
| ---------------------- | ------------------------------------- | ---- | -------------------------------- | ------------------------------------------ |
| `model`                | `execution.config.model`              | 是   | `midjourney/v8.1/image-to-video` | 工作机从执行配置读取                       |
| `image`                | `first_frame` 或 `first_frame_source` | 是   | —                                | 上传首帧图片或提供公开 HTTPS 图片地址      |
| `prompt`               | `prompt`                              | 否   | Schema 提供可编辑示例            | 描述主体动作、镜头运动或场景变化           |
| `resolution`           | `resolution`                          | 否   | `480p`                           | `480p` 或 `720p`。720p 按 480p 的 3 倍计费 |
| `motion`               | `motion`                              | 否   | `low`                            | `low` 低运动，`high` 高运动                |
| `enable_base64_output` | `enable_base64_output`                | 否   | `false`                          | 工作机将 Base64 MP4 解码后保存             |

Atlas 每次返回四段固定 5 秒的视频，宽高比沿用输入图片。视频可以按 URL 下载，也可以从响应中的 Base64 数据保存。

[官方 Schema](https://static.atlascloud.ai/model/schema/midjourney-v8.1-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/midjourney-v8.1-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/midjourney-v8.1-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/midjourney/v8.1/image-to-video#usage-examples)

```json
{
  "model": "midjourney/v8.1/image-to-video",
  "image": "https://example.com/lantern.png",
  "prompt": "镜头缓慢推进，灯笼轻轻摇动。",
  "resolution": "480p",
  "motion": "low",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存四段视频，支持公开 HTTPS 输出以及 Base64 MP4。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首帧图片、提示词、分辨率和运动幅度。高级参数为首帧图片 URL 和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
