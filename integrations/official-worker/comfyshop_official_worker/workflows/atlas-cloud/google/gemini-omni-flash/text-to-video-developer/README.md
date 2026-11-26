# Gemini Omni Flash Developer 文生视频

从文字生成带音频的视频，可选时长、宽高比和最高 4K 分辨率。 Atlas Cloud 模型 ID 为 `google/gemini-omni-flash/text-to-video-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-flash/text-to-video-developer)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                                             | 输入约定                    |
| -------------- | ------------------------ | ---- | -------------------------------------------------- | --------------------------- |
| `model`        | `execution.config.model` | 是   | `google/gemini-omni-flash/text-to-video-developer` | 工作机从执行配置读取        |
| `prompt`       | `prompt`                 | 是   | 无                                                 | 最多 20,000 字符            |
| `duration`     | `duration`               | 否   | 8                                                  | `4`、`6`、`8` 或 `10` 秒    |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                                             | `16:9` 或 `9:16`            |
| `resolution`   | `resolution`             | 否   | `720p`                                             | `720p`、`1080p` 或 `4k`     |
| `seed`         | `seed`                   | 否   | -1                                                 | 整数。-1 由模型随机选取种子 |

模型同时生成画面和声音。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-flash-text-to-video-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-flash-text-to-video-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-flash-text-to-video-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-flash/text-to-video-developer#usage-examples)

```json
{
  "model": "google/gemini-omni-flash/text-to-video-developer",
  "prompt": "雨后的清晨，镜头沿石板路缓缓推进。街灯倒映在水坑里，远处有轻微的电车声。",
  "duration": 8,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、时长、比例和分辨率位于默认区。随机种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
