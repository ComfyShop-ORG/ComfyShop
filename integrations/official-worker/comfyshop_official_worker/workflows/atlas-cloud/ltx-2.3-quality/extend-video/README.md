# LTX 2.3 Quality 视频延长

根据提示词在原视频前后生成新画面，可匹配原片帧率并生成音频。 Atlas Cloud 模型 ID 为 `ltx-2.3-quality/extend-video`。[官方模型 API](https://www.atlascloud.ai/models/ltx-2.3-quality/extend-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                       | 必填 | 默认值                         | 输入约定                                                                                  |
| ------------------ | ------------------------------------ | ---- | ------------------------------ | ----------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`             | 是   | `ltx-2.3-quality/extend-video` | 工作机从执行配置读取                                                                      |
| `video_url`        | `source_video` 或 `source_video_url` | 是   | —                              | MP4、MOV、WebM、M4V、GIF，上传或公开 URL                                                  |
| `prompt`           | `prompt`                             | 是   | Schema 提供可编辑示例          | 非空文字，1 至 2,000 字符                                                                 |
| `extend_direction` | `extend_direction`                   | 否   | `forward`                      | `forward` 在原片之后追加，`backward` 在原片之前补齐                                       |
| `num_frames`       | `num_frames`                         | 否   | `81`                           | 整数 9–481，满足 `(num_frames - 1) % 8 == 0`                                              |
| `resolution`       | `resolution`                         | 否   | `landscape_16_9`               | `square_hd`、`square`、`portrait_3_4`、`portrait_9_16`、`landscape_4_3`、`landscape_16_9` |
| `match_input_fps`  | `match_input_fps`                    | 否   | `true`                         | 沿用原视频帧率                                                                            |
| `generate_audio`   | `generate_audio`                     | 否   | `false`                        | 生成同步音频                                                                              |
| `seed`             | `seed`                               | 否   | 由 Atlas 选取                  | 非负整数，留空时省略参数                                                                  |

调用方法采用官方模型页和端点文档中的 `generateVideo`。原视频可用上传或公开 URL 传入。

[官方 Schema](https://static.atlascloud.ai/model/schema/ltx-2.3-quality-extend-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/ltx-2.3-quality-extend-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/ltx-2.3-quality-extend-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/ltx-2.3-quality/extend-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/ltx-2.3-quality/extend-video#usage-examples)

```json
{
  "model": "ltx-2.3-quality/extend-video",
  "video_url": "https://example.com/source.mp4",
  "prompt": "镜头继续向前，从树林走到开阔的山谷。",
  "extend_direction": "forward",
  "num_frames": 81,
  "resolution": "landscape_16_9",
  "match_input_fps": true,
  "generate_audio": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原视频、提示词、延长方向、续接帧数和画面尺寸。高级参数为匹配帧率、同步音频、随机种子及原视频 URL。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
