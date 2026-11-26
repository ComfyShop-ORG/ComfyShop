# Veo 3.1 Lite 文生视频

用文字生成 720p 或 1080p 视频，提示词可包含对白、音效及环境声。 Atlas Cloud 模型 ID 为 `google/veo3.1-lite/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/veo3.1-lite/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                             |
| -------------- | ------------------------ | ---- | ---------------------------------- | ------------------------------------ |
| `model`        | `execution.config.model` | 是   | `google/veo3.1-lite/text-to-video` | 工作机从执行配置读取                 |
| `prompt`       | `prompt`                 | 是   | 无                                 | 描述主体、场景及镜头，可附加音频提示 |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                             | `16:9` 或 `9:16`                     |
| `duration`     | `duration`               | 否   | 8                                  | `4`、`6` 或 `8` 秒。1080p 时为 8 秒  |
| `resolution`   | `resolution`             | 否   | `720p`                             | `720p` 或 `1080p`                    |
| `seed`         | `seed`                   | 否   | -1                                 | 整数。-1 由模型随机选取种子          |

工作机按分辨率校验时长。1080p 固定为 8 秒。示例成品使用 `.f4v` 扩展名，平台读取实际容器和视频流识别文件。[官方 Schema](https://static.atlascloud.ai/model/schema/google-veo3.1-lite-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-veo3.1-lite-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-veo3.1-lite-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/veo3.1-lite/text-to-video#usage-examples)

```json
{
  "model": "google/veo3.1-lite/text-to-video",
  "prompt": "镜头从窗台拉远，露出雨后的街道。加入雨滴落在水洼的声音和远处的电车铃声。",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "duration": 8,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、比例、分辨率和时长位于默认区。随机种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
