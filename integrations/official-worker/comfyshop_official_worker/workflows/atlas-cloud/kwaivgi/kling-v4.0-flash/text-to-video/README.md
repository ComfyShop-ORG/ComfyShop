# 可灵 4.0 Flash 文生视频

用文字生成 3 至 20 秒的 720p 视频，可选横屏、竖屏、方形和宽银幕比例。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0-flash/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                                   | 输入约定                                                            |
| -------------- | ------------------------ | ---- | ---------------------------------------- | ------------------------------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `kwaivgi/kling-v4.0-flash/text-to-video` | 工作机从执行配置读取                                                |
| `prompt`       | `prompt`                 | 是   | 官方示例                                 | 描述主体、动作、环境和镜头。英文最多 26,000 字符，非英文最多 11,000 |
| `duration`     | `duration`               | 否   | 10                                       | 3 至 20 秒的整数                                                    |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                                   | `16:9`、`9:16`、`1:1`、`21:9`                                       |
| `resolution`   | `resolution`             | 否   | `720p`                                   | 固定 `720p`                                                         |

表单保留同一条可编辑的官方英文提示词。工作机检查提示词总长度，Atlas 检查语言对应的上限。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-flash-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-flash-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-flash-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0-flash/text-to-video",
  "prompt": "一点雨水从叶尖滴入浅盘，微距镜头拍出向外扩散的水波。",
  "duration": 10,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例和时长位于默认区。固定分辨率由工作机提交。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
