# MiniMax H3 文生视频

根据提示词生成视频，可设置时长、分辨率、画面比例和提示词扩写。 Atlas Cloud 模型 ID 为 `minimax/h3/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/minimax/h3/text-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                     | 输入约定                                    |
| ------------------ | ------------------------ | ---- | -------------------------- | ------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3/text-to-video` | 工作机从执行配置读取                        |
| `prompt`           | `prompt`                 | 是   | —                          | 描述画面、动作、场景和声音                  |
| `duration`         | `duration_seconds`       | 是   | `8`                        | 整数 4 至 15 秒                             |
| `resolution`       | `resolution`             | 是   | `2K`                       | `480P`、`768P`、`2K`                        |
| `ratio`            | `aspect_ratio`           | 是   | `1:1`                      | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                    | 使用 H3 Context-IR 扩写，按 Token 另行计费  |

本模型说明要求文生视频发送明确的 `ratio`。静态示例数据中的 `adaptive`、`image` 和 `end_image` 对应图像模式，使用模型 API 页文生视频示例中的字段和值。

[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/minimax-h3-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/minimax/h3-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/minimax/h3/text-to-video#usage-examples)

```json
{
  "model": "minimax/h3/text-to-video",
  "prompt": "微风吹过山间草地，镜头贴着草尖推进，保留风声。",
  "duration": 8,
  "resolution": "2K",
  "ratio": "1:1",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、分辨率和画面比例。高级参数为提示词扩写。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
