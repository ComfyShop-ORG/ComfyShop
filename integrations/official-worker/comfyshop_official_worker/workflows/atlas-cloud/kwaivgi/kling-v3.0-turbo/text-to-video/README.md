# 可灵 3.0 Turbo 文生视频

从文字生成 3 至 15 秒的视频，可选择横屏、竖屏或方形画面。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v3.0-turbo/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-turbo/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                                   | 输入约定                                    |
| -------------- | ------------------------ | ---- | ---------------------------------------- | ------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `kwaivgi/kling-v3.0-turbo/text-to-video` | 工作机从执行配置读取                        |
| `prompt`       | `prompt`                 | 是   | 无                                       | 描述主体、场景、动作和运镜，最多 2,500 字符 |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                                   | `16:9`、`9:16` 或 `1:1`                     |
| `duration`     | `duration`               | 否   | 5                                        | 3 至 15 秒，整数枚举                        |
| `resolution`   | `resolution`             | 否   | `1080p`                                  | `720p` 或 `1080p`                           |

工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v3.0-turbo-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v3.0-turbo-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v3.0-turbo-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v3.0-turbo-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-turbo/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v3.0-turbo/text-to-video",
  "prompt": "清晨的山路静静延伸，镜头缓慢掠过远处的树梢。",
  "aspect_ratio": "16:9",
  "duration": 5,
  "resolution": "1080p"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例、分辨率和时长均位于默认区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
