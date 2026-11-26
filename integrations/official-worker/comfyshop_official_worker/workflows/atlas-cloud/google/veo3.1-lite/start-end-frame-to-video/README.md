# Veo 3.1 Lite 首尾帧生视频

用首尾两张图和提示词生成中间过渡，可描述同步音频。 Atlas Cloud 模型 ID 为 `google/veo3.1-lite/start-end-frame-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/veo3.1-lite/start-end-frame-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                        | 必填 | 默认值                                        | 输入约定                                                                       |
| -------------- | ------------------------------------- | ---- | --------------------------------------------- | ------------------------------------------------------------------------------ |
| `model`        | `execution.config.model`              | 是   | `google/veo3.1-lite/start-end-frame-to-video` | 工作机从执行配置读取                                                           |
| `prompt`       | `prompt`                              | 是   | 无                                            | 描述两帧之间的运动、镜头和声音                                                 |
| `image`        | `first_frame` 或 `first_frame_source` | 是   | 无                                            | 一张最多 8 MB 的 PNG 或 JPEG。接受上传、公开 URL、Base64 数据网址或原始 Base64 |
| `last_image`   | `last_frame` 或 `last_frame_source`   | 是   | 无                                            | 一张最多 8 MB 的结束图。格式与来源规则与起始图相同                             |
| `aspect_ratio` | `aspect_ratio`                        | 否   | `16:9`                                        | `16:9` 或 `9:16`                                                               |
| `duration`     | `duration`                            | 否   | 8                                             | `4`、`6` 或 `8` 秒。1080p 时为 8 秒                                            |
| `resolution`   | `resolution`                          | 否   | `720p`                                        | `720p` 或 `1080p`                                                              |
| `seed`         | `seed`                                | 否   | -1                                            | 整数。-1 由模型随机选取种子                                                    |

文本来源框最多容纳 4,194,304 个字符。更大的图片可通过上传或公开 URL 提供。首帧和尾帧同时提交，文件限制分别生效。[官方 Schema](https://static.atlascloud.ai/model/schema/google-veo3.1-lite-start-end-frame-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-veo3.1-lite-start-end-frame-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-veo3.1-lite-start-end-frame-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/google/veo3.1-lite-start-end-frame-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/google/veo3.1-lite/start-end-frame-to-video#usage-examples)

```json
{
  "model": "google/veo3.1-lite/start-end-frame-to-video",
  "prompt": "镜头在第一帧缓慢推进，花瓣依次绽放，过渡到最后一帧。",
  "image": "https://example.com/opening.png",
  "last_image": "https://example.com/closing.png",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "duration": 8,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首尾图片、比例、分辨率和时长位于默认区。图片来源和随机种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
