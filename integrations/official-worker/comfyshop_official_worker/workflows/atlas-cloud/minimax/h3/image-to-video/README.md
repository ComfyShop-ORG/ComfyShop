# MiniMax H3 图生视频

用首帧图片和提示词生成视频，可选尾帧固定结尾。 Atlas Cloud 模型 ID 为 `minimax/h3/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/minimax/h3/image-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                        | 必填 | 默认值                      | 输入约定                                                 |
| ------------------ | ------------------------------------- | ---- | --------------------------- | -------------------------------------------------------- |
| `model`            | `execution.config.model`              | 是   | `minimax/h3/image-to-video` | 工作机从执行配置读取                                     |
| `prompt`           | `prompt`                              | 是   | —                           | 描述画面变化、动作或镜头运动                             |
| `image`            | `first_frame` 或 `first_frame_source` | 是   | —                           | 首帧图片，PNG、JPEG 或 WebP                              |
| `end_image`        | `last_frame` 或 `last_frame_source`   | 否   | —                           | 尾帧图片，PNG、JPEG 或 WebP                              |
| `duration`         | `duration_seconds`                    | 是   | `8`                         | 整数 4 至 15 秒                                          |
| `resolution`       | `resolution`                          | 是   | `2K`                        | `480P`、`768P`、`2K`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `ratio`            | `aspect_ratio`（隐藏）                | 否   | `adaptive`                  | 由首帧确定画面比例                                       |
| `prompt_expansion` | `expand_prompt`                       | 否   | `false`                     | 使用 H3 Context-IR 扩写，按 Token 另计费                 |

模型说明要求首帧和提示词。图片可上传，或填写公开 URL、原始 Base64 或 Data URI。Base64 超过文本输入容量时可直接上传。`480P`、`768P` 和 `2K` 为原生档位，`1080p-esr`、`1440p-esr` 与 `4k-esr` 均由原生 `768P` 增强生成，按所选档位计费。

[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/minimax-h3-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/minimax/h3-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/minimax/h3/image-to-video#usage-examples)

```json
{
  "model": "minimax/h3/image-to-video",
  "prompt": "微风吹动纸灯笼，镜头缓慢拉远。",
  "image": "https://example.com/start.png",
  "end_image": "https://example.com/end.png",
  "duration": 8,
  "resolution": "2K",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首尾帧、提示词、时长和分辨率。高级参数为外部图片来源和扩写。自适应比例在任务表单中隐藏。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
