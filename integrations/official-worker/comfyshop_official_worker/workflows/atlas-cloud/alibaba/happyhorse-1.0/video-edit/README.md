# HappyHorse 1.0 视频编辑

按提示词编辑原视频，可用参考图引导画面，并选择音频处理方式。 Atlas Cloud 模型 ID 为 `alibaba/happyhorse-1.0/video-edit`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/video-edit)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                      | 必填 | 默认值                              | 输入约定                                                              |
| --------------- | --------------------------------------------------- | ---- | ----------------------------------- | --------------------------------------------------------------------- |
| `model`         | `execution.config.model`                            | 是   | `alibaba/happyhorse-1.0/video-edit` | 工作机从执行配置读取                                                  |
| `video`         | `video` 或 `video_source`                           | 是   | 无                                  | MP4 或 MOV，3 至 60 秒，最大 100 MB。上传原片或填公开 URL             |
| `prompt`        | `prompt`                                            | 是   | 无                                  | 说明需要编辑的内容，最多 2,500 字符                                   |
| `images`        | `reference_1` 至 `reference_5`、`reference_sources` | 否   | 无                                  | 至多五张 JPEG、PNG、BMP 或 WebP，长短边比例最多 2.5:1，单张最多 10 MB |
| `resolution`    | `resolution`                                        | 否   | `1080p`                             | `720p` 或 `1080p`                                                     |
| `audio_setting` | `audio_setting`                                     | 否   | `auto`                              | `auto` 由模型处理音频。`origin` 保留原音轨                            |
| `seed`          | `seed`                                              | 否   | -1                                  | 整数范围 -1 至 2147483647。-1 使用随机种子                            |

工作机将上传原件转换成素材地址。Atlas 对超过 15 秒的原视频处理开头 15 秒。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-happyhorse-1.0-video-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-happyhorse-1.0-video-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-happyhorse-1.0-video-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/video-edit#usage-examples)

```json
{
  "model": "alibaba/happyhorse-1.0/video-edit",
  "video": "https://example.com/greenhouse.mp4",
  "prompt": "给温室换成傍晚的暖光，保留镜头移动和人物动作。",
  "images": ["https://example.com/warm-light.jpg"],
  "resolution": "1080p",
  "audio_setting": "origin",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、提示词、第一张参考图和分辨率位于默认区。其他参考图、素材地址、音频和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
