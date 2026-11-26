# Vidu Q4 Preview 参考生视频

根据参考图和可选的音频片段生成 3 至 16 秒的视频，支持最高 4K。 Atlas Cloud 模型 ID 为 `vidu/q4-preview/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q4-preview/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                               | 必填 | 默认值                               | 输入约定                                                                                    |
| ------------------ | ------------------------------------------------------------ | ---- | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                     | 是   | `vidu/q4-preview/reference-to-video` | 工作机从执行配置读取                                                                        |
| `reference_images` | `reference_image_1` 至 `reference_image_15`、`image_sources` | 是   | 无                                   | 1 至 15 张 JPEG、PNG 或 WebP，每张最多 50 MB。上传、公开 URL 或带媒体类型的 Base64 数据网址 |
| `reference_audios` | `reference_audio_1` 至 `reference_audio_3`、`audio_sources`  | 否   | 省略                                 | 最多 3 条 MP3，每条 3 至 12 秒且不超过 50 MB。上传或公开 URL                                |
| `prompt`           | `prompt`                                                     | 是   | 官方示例                             | 最多 20,000 字符，以 `@1`、`@2` 等引用各图片                                                |
| `duration`         | `duration`                                                   | 否   | 5                                    | 3 至 16 秒的整数                                                                            |
| `aspect_ratio`     | `aspect_ratio`                                               | 否   | `16:9`                               | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`                                                         |
| `resolution`       | `resolution`                                                 | 否   | `720p`                               | `540p`、`720p`、`1080p`、`2k`、`4k`                                                         |
| `generate_audio`   | `generate_audio`                                             | 否   | `true`                               | 是否生成同步对白、音效和环境声                                                              |
| `seed`             | `seed`                                                       | 否   | -1                                   | 整数，-1 使用随机种子                                                                       |

在图片列表中先按上传栏位排序，再追加逐行填写的来源，并从 `@1` 开始编号。音频也先提交上传栏位，再追加外部来源。ComfyShop 的图片来源字段限制为 4 MiB。工作流采用当前请求 Schema，静态示例数据还包含 `watermark`。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q4-preview-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q4-preview-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q4-preview-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/vidu/q4-preview/reference-to-video#usage-examples)

```json
{
  "model": "vidu/q4-preview/reference-to-video",
  "reference_images": ["https://example.com/traveler.png", "https://example.com/ferry.png"],
  "reference_audios": ["https://example.com/harbor.mp3"],
  "prompt": "镜头跟随 @1 走上 @2 中的轮渡，环境声逐渐变成轻柔的海浪。",
  "duration": 5,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "generate_audio": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

首张参考图、提示词、画面比例、分辨率和时长位于默认区。其余图片、图片来源、音频、同步音频开关及种子位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
