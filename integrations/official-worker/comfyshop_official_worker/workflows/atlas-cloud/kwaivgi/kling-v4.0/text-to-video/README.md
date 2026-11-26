# 可灵 4.0 文生视频

根据文字生成 3 至 30 秒的视频，支持原生 4K、腾讯 ESR 超分和 10 位 HDR。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/text-to-video)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                                                                                      |
| --------------- | ------------------------ | ---- | ---------------------------------- | --------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `kwaivgi/kling-v4.0/text-to-video` | 工作机从执行配置读取                                                                          |
| `prompt`        | `prompt`                 | 是   | 官方示例                           | 描述主体、环境、动作和运镜，可一并描述希望避免的内容。英文最多 26,000 字符，非英文最多 11,000 |
| `duration`      | `duration`               | 否   | 10                                 | 3 至 30 秒的整数                                                                              |
| `aspect_ratio`  | `aspect_ratio`           | 否   | `16:9`                             | `16:9`、`9:16`、`1:1`、`21:9`                                                                 |
| `resolution`    | `resolution`             | 否   | `1080p`                            | `720p`、`1080p`、`4k`、`1080p-esr`、`2k-esr`、`4k-esr`                                        |
| `dynamic_range` | `dynamic_range`          | 否   | `sdr`                              | `sdr` 或 `hdr`。10 位 HDR 只用于原生 `1080p` 或 `4k`                                          |

工作机检查提示词总长度，Atlas 检查语言对应的上限。ESR 保留原始宽高比，Atlas 分别计收视频生成和增强费用。HDR 按输出秒数计收附加费用。 [官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0/text-to-video",
  "prompt": "一滴露水从蓝莓叶尖落下，微距跟随水滴并定格杯中的涟漪。",
  "duration": 10,
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "dynamic_range": "sdr"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例、时长、分辨率和动态范围位于默认区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
