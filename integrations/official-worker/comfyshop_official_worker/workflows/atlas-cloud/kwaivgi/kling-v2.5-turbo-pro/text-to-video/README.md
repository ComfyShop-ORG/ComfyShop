# 可灵 2.5 Turbo 专业版文生视频

将文字描述生成 5 或 10 秒的视频，可选择横屏、竖屏或方形画面。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v2.5-turbo-pro/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v2.5-turbo-pro/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                                       | 输入约定                                    |
| -------------- | ------------------------ | ---- | -------------------------------------------- | ------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `kwaivgi/kling-v2.5-turbo-pro/text-to-video` | 工作机从执行配置读取                        |
| `prompt`       | `prompt`                 | 是   | 无                                           | 描述主体、场景、动作和镜头，最多 2,500 字符 |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                                       | `16:9`、`9:16` 或 `1:1`                     |
| `duration`     | `duration`               | 否   | 5                                            | `5` 或 `10` 秒                              |

工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v2.5-turbo-pro-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v2.5-turbo-pro-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v2.5-turbo-pro-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v2.5-turbo-pro-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v2.5-turbo-pro/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v2.5-turbo-pro/text-to-video",
  "prompt": "细雨后的石板路映出路灯，镜头从脚边的水洼缓缓升向夜色。",
  "aspect_ratio": "16:9",
  "duration": 5
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例和时长位于默认区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
