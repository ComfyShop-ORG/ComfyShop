# 可灵 O3 专业版视频编辑

用文字指令编辑原视频，可用参考图引导画面，也可指定已有音色。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-video-o3-pro/video-edit`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/video-edit)

## Atlas 接口参数

| Atlas 参数            | ComfyShop 字段                                      | 必填 | 默认值                                  | 输入约定                                                                                                                   |
| --------------------- | --------------------------------------------------- | ---- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `model`               | `execution.config.model`                            | 是   | `kwaivgi/kling-video-o3-pro/video-edit` | 工作机从执行配置读取                                                                                                       |
| `video`               | `source_video` 或 `video_source`                    | 是   | 无                                      | MP4 或 MOV，3 至 15.5 秒、24 至 60 帧每秒、最多 200 MB。每边 700 至 4,553 像素，总面积最多 8,294,400 像素，宽高比 0.4 至 2 |
| `prompt`              | `prompt`                                            | 是   | 无                                      | 最多 2,500 字符，描述编辑内容。可用 `<<<video_1>>>`、`<<<image_1>>>` 等引用素材                                            |
| `images`              | `reference_1` 至 `reference_4`、`reference_sources` | 否   | 省略                                    | 最多 4 张 JPEG 或 PNG，每张最多 50 MB。每边至少 300 像素，宽高比 1:2.5 至 2.5:1                                            |
| `voice_ids`           | `voice_ids`                                         | 否   | 省略                                    | 最多 3 个已有或预设可灵音色 ID。每行一个，原样发送字符串                                                                   |
| `keep_original_sound` | `keep_original_sound`                               | 否   | `true`                                  | 保留原视频的声音                                                                                                           |

工作机先按可用的宽高和时长元数据校验上传视频，帧率由 Atlas 校验。可选图片先提交上传项，再提交图片 URL，跳过空槽，以提交顺序从 `<<<image_1>>>` 开始编号。音色用 `<<<voice_1>>>` 或 `@voice_1` 等引用。原生输出 1080p、每秒 24 帧，时长跟随原视频。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[可灵自定义音色](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice) · [官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-video-o3-pro-video-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-video-o3-pro-video-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-video-o3-pro-video-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-video-o3-pro-video-edit/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/video-edit#usage-examples)

```json
{
  "model": "kwaivgi/kling-video-o3-pro/video-edit",
  "video": "https://example.com/clip.mp4",
  "images": ["https://example.com/reference.jpg"],
  "prompt": "把 <<<video_1>>> 的背景色调调整为 <<<image_1>>> 中的淡紫色，保持镜头节奏。",
  "keep_original_sound": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、编辑指令和第一张参考图位于默认区。更多参考图、素材 URL、音色 ID 和声音保留位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
