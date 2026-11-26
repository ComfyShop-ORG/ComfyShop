# Gemini Omni Flash Developer 参考生视频

用原视频片段和提示词生成新视频，可另加参考图。 Atlas Cloud 模型 ID 为 `google/gemini-omni-flash/reference-to-video-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video-developer)

## Atlas 接口参数

| Atlas 参数            | ComfyShop 字段                                                        | 必填 | 默认值                                                  | 输入约定                                                        |
| --------------------- | --------------------------------------------------------------------- | ---- | ------------------------------------------------------- | --------------------------------------------------------------- |
| `model`               | `execution.config.model`                                              | 是   | `google/gemini-omni-flash/reference-to-video-developer` | 工作机从执行配置读取                                            |
| `prompt`              | `prompt`                                                              | 是   | 无                                                      | 最多 20,000 字符                                                |
| `video_clips`         | `video`、`video_source`、`video_start`、`video_end`                   | 是   | 无                                                      | 恰好一个 `{url,start,ends}` 对象。原视频最长 30 秒、最大 100 MB |
| `video_clips[].url`   | `video` 或 `video_source`                                             | 是   | 无                                                      | 上传原视频获取 Atlas 地址，或填写公开视频 URL                   |
| `video_clips[].start` | `video_start`                                                         | 是   | 0                                                       | 剪辑开始秒数，整数 0 至 29                                      |
| `video_clips[].ends`  | `video_end`                                                           | 是   | 10                                                      | 剪辑结束秒数，整数 1 至 30。必须晚于 `start`，差值最多 10 秒    |
| `images`              | `reference_image_1` 至 `reference_image_5`、`reference_image_sources` | 否   | 无                                                      | 一至五个公开图片 URL。支持 PNG、JPEG 或 WebP，单张最多 20 MB    |
| `duration`            | `duration`                                                            | 否   | 8                                                       | `4`、`6`、`8` 或 `10` 秒                                        |
| `aspect_ratio`        | `aspect_ratio`                                                        | 否   | `16:9`                                                  | `16:9` 或 `9:16`                                                |
| `resolution`          | `resolution`                                                          | 否   | `720p`                                                  | `720p`、`1080p` 或 `4k`                                         |
| `seed`                | `seed`                                                                | 否   | -1                                                      | 整数。-1 由模型随机选取种子                                     |

原视频占七个参考素材配额中的两个，剩余最多五张图片。工作流采用请求 Schema 和调用示例中的 `ends` 字段，并将图片作为可选素材。模型说明将结束字段写为 `end`，将图片列为必填。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-flash-reference-to-video-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-flash-reference-to-video-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-flash-reference-to-video-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/google/gemini-omni-flash-reference-to-video-developer/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video-developer#usage-examples)

```json
{
  "model": "google/gemini-omni-flash/reference-to-video-developer",
  "prompt": "沿用原视频的推镜节奏，将桌上的花瓶替换成参考图里的陶瓷杯。",
  "video_clips": [
    {
      "url": "https://example.com/input.mp4",
      "start": 1,
      "ends": 9
    }
  ],
  "images": ["https://example.com/cup.webp"],
  "duration": 8,
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、原视频、第一张参考图、时长、比例和分辨率位于默认区。剪辑时间、其他参考图、素材地址与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
