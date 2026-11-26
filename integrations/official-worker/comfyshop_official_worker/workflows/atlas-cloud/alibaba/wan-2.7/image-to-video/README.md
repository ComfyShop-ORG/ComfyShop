# Wan 2.7 图生视频与续写

用起始图生成视频，或续写原视频。两种模式均可指定结束帧。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/image-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                        | 必填     | 默认值                           | 输入约定                                                                               |
| ----------------- | ------------------------------------- | -------- | -------------------------------- | -------------------------------------------------------------------------------------- |
| `model`           | `execution.config.model`              | 是       | `alibaba/wan-2.7/image-to-video` | 工作机从执行配置读取                                                                   |
| `image`           | `first_frame` 或 `first_frame_source` | 条件必填 | 无                               | 起始帧。在起始帧和原视频之间选择一项                                                   |
| `last_image`      | `last_frame` 或 `last_frame_source`   | 否       | 无                               | 用于约束最后一帧                                                                       |
| `video`           | `video` 或 `video_source`             | 条件必填 | 无                               | 续写原片，MP4 或 MOV，2 至 10 秒、最多 100 MB                                          |
| `audio`           | `soundtrack` 或 `soundtrack_source`   | 否       | 无                               | 起始帧模式的驱动音频。WAV 或 MP3，2 至 30 秒、最多 15 MB。Atlas 也接受别名 `audio_url` |
| `prompt`          | `prompt`                              | 否       | 无                               | 最多 5,000 字符                                                                        |
| `negative_prompt` | `negative_prompt`                     | 否       | 无                               | 最多 500 字符                                                                          |
| `resolution`      | `resolution`                          | 否       | `1080P`                          | 原生 `720P` 或 `1080P`。FlashVSR `1080P-SR` 或 `1440P-SR`                              |
| `duration`        | `duration`                            | 否       | 5                                | 2 至 15 秒的整数                                                                       |
| `prompt_extend`   | `prompt_extend`                       | 否       | true                             | 由模型扩写提示词                                                                       |
| `seed`            | `seed`                                | 否       | -1                               | 整数范围 -1 至 2147483647。-1 使用随机种子                                             |

首尾帧接受 JPEG、无透明通道的 PNG、BMP 或 WebP。宽高各 240 至 8000 像素，长短边比例最多 8:1，每张最多 20 MB。工作机校验起始帧与原视频二选一，驱动音频用于起始帧模式。任一模式可选结束帧，画面比例沿用起始素材。素材可上传或填写公开 URL。Atlas 模型说明补充了两个 FlashVSR 分辨率值。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/image-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/image-to-video",
  "image": "https://example.com/cafe-start.jpg",
  "last_image": "https://example.com/cafe-end.jpg",
  "audio": "https://example.com/line.wav",
  "prompt": "从入口向窗边移动镜头，人物随音频开口。",
  "resolution": "1080P-SR",
  "duration": 8,
  "prompt_extend": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始帧、结束帧、原视频、提示词、分辨率和时长位于默认区。素材地址、驱动音频、负面提示词、扩写和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
