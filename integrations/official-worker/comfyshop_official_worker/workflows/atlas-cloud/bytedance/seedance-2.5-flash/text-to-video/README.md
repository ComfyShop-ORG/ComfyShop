# Seedance 2.5 Flash 文生视频

Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5-flash/text-to-video`。请求字段和枚举见官方 Schema。[官方 API 页](https://www.atlascloud.ai/zh/models/bytedance/seedance-2.5-flash/text-to-video?tab=api) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.5-flash-text-to-video.json)

## 字段和请求

| ComfyShop 字段       | Atlas 参数          | 初始值   | 说明                        |
| -------------------- | ------------------- | -------- | --------------------------- |
| `prompt`             | `prompt`            | 用户填写 | 文本提示词                  |
| `duration_seconds`   | `duration`          | `5`      | 4 至 30 秒，`-1` 为自动时长 |
| `aspect_ratio`       | `ratio`             | `16:9`   | 六种固定比例及 `adaptive`   |
| `resolution`         | `resolution`        | `720p`   | `480p` 或 `720p`            |
| `generate_audio`     | `generate_audio`    | `true`   | 生成同步音频                |
| `add_watermark`      | `watermark`         | `false`  | 叠加水印                    |
| `include_last_frame` | `return_last_frame` | `false`  | 单独交付尾帧图片            |
| `video_format`       | `output_format`     | `mp4`    | `mp4` 或 `mov`              |

工作流将提示词、时长、比例和分辨率放在默认区，将其余设置放在高级区。工作机从 `execution.config.model` 带入 `model`，向 `POST https://api.atlascloud.ai/api/v1/model/generateVideo` 发送 JSON。请求使用 `Authorization: Bearer <API_KEY>`。[视频生成 API](https://www.atlascloud.ai/docs/en/models/video)

```json
{
  "model": "bytedance/seedance-2.5-flash/text-to-video",
  "prompt": "雨后清晨，镜头沿山间铁路缓慢推进。",
  "duration": 5,
  "ratio": "16:9",
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "return_last_frame": true,
  "output_format": "mp4"
}
```

从提交响应读取 `data.id` 后，轮询 `GET /api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载视频。开启尾帧时，工作流通过 `additionalOutputKinds` 接收同一次执行返回的图片。[预测文档](https://www.atlascloud.ai/docs/en/predictions)

## 参数布局与译文

工作流标识为 `seedance-25-flash-text-to-video`。维护账号可通过「编辑参数」保存当前版本的分组、控件、提示和默认值。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../../docs/deployment.md#官方工作机)
