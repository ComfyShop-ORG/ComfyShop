# Gemini Omni Flash Developer 图生视频

用提示词与一至七张参考图生成视频，可选 720p 至 4K。 Atlas Cloud 模型 ID 为 `google/gemini-omni-flash/image-to-video-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-flash/image-to-video-developer)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                                                        | 必填 | 默认值                                              | 输入约定                                                     |
| -------------- | --------------------------------------------------------------------- | ---- | --------------------------------------------------- | ------------------------------------------------------------ |
| `model`        | `execution.config.model`                                              | 是   | `google/gemini-omni-flash/image-to-video-developer` | 工作机从执行配置读取                                         |
| `prompt`       | `prompt`                                                              | 是   | 无                                                  | 最多 20,000 字符                                             |
| `images`       | `reference_image_1` 至 `reference_image_7`、`reference_image_sources` | 是   | 无                                                  | 一至七个公开图片 URL。支持 PNG、JPEG 或 WebP，每张最多 20 MB |
| `duration`     | `duration`                                                            | 否   | 8                                                   | `4`、`6`、`8` 或 `10` 秒                                     |
| `aspect_ratio` | `aspect_ratio`                                                        | 否   | `16:9`                                              | `16:9` 或 `9:16`                                             |
| `resolution`   | `resolution`                                                          | 否   | `720p`                                              | `720p`、`1080p` 或 `4k`                                      |
| `seed`         | `seed`                                                                | 否   | -1                                                  | 整数。-1 由模型随机选取种子                                  |

工作机将上传图转换成 Atlas 素材地址，再按行追加手工填写的公开图片地址。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-flash-image-to-video-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-flash-image-to-video-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-flash-image-to-video-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-flash/image-to-video-developer#usage-examples)

```json
{
  "model": "google/gemini-omni-flash/image-to-video-developer",
  "prompt": "让参考图里的陶瓷杯在窗边缓慢转动。镜头由近到远，保持釉面反光。",
  "images": ["https://example.com/cup.webp"],
  "duration": 8,
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、时长、比例和分辨率位于默认区。其余参考图、图片网址和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
