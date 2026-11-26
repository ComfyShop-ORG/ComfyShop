# Veo 3.1 参考生视频

用一至三张参考图和提示词生成 8 秒视频，保持主体一致。 Atlas Cloud 模型 ID 为 `google/veo3.1/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/veo3.1/reference-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                                                        | 必填 | 默认值                             | 输入约定                                                                                                         |
| ----------------- | --------------------------------------------------------------------- | ---- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `model`           | `execution.config.model`                                              | 是   | `google/veo3.1/reference-to-video` | 工作机从执行配置读取                                                                                             |
| `prompt`          | `prompt`                                                              | 是   | 无                                 | 描述参考主体、场景和镜头                                                                                         |
| `images`          | `reference_image_1` 至 `reference_image_3`、`reference_image_sources` | 是   | 无                                 | 一至三张 PNG、JPEG 或 WebP。每边至少 128 像素，每张最多 50 MB。接受上传、公开 URL 或带媒体类型的 Base64 数据网址 |
| `duration`        | `duration`                                                            | 否   | 8                                  | 固定为 8 秒                                                                                                      |
| `resolution`      | `resolution`                                                          | 否   | `720p`                             | `720p`、`1080p` 或 `4k`                                                                                          |
| `generate_audio`  | `generate_audio`                                                      | 否   | false                              | 同时生成音频                                                                                                     |
| `negative_prompt` | `negative_prompt`                                                     | 否   | 无                                 | 描述应避开的画面元素，留空时省略                                                                                 |
| `seed`            | `seed`                                                                | 否   | 由 Atlas 选择                      | 整数，留空时省略                                                                                                 |

工作机先排列上传图，再添加手工填写的图片来源。官方要求内联 Base64 解码后小于 50 MB。ComfyShop 的文本来源框最多容纳 4,194,304 个字符。时长采用端点 Schema 的 8 秒，模型介绍中另有 5 秒表述。工作机按调用示例使用 `prediction/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/google-veo3.1-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-veo3.1-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-veo3.1-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/veo3.1/reference-to-video#usage-examples)

```json
{
  "model": "google/veo3.1/reference-to-video",
  "prompt": "镜头从侧面跟随参考图里的蓝色自行车缓慢经过河堤。保留车架外观，加入清晰的车轮转动与风声。",
  "images": ["https://example.com/bicycle.webp"],
  "resolution": "1080p",
  "duration": 8,
  "generate_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图和分辨率位于默认区。其他参考图、图片来源、音频、负面提示词和种子位于高级区。时长是隐藏参数。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
