# Wan 2.7 文生视频

根据提示词生成最多 15 秒的视频，可选配乐与超分辨率。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/text-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                      | 必填 | 默认值                          | 输入约定                                                                                    |
| ----------------- | ----------------------------------- | ---- | ------------------------------- | ------------------------------------------------------------------------------------------- |
| `model`           | `execution.config.model`            | 是   | `alibaba/wan-2.7/text-to-video` | 工作机从执行配置读取                                                                        |
| `prompt`          | `prompt`                            | 是   | 无                              | 描述画面、动作和镜头，最多 5,000 字符                                                       |
| `negative_prompt` | `negative_prompt`                   | 否   | 无                              | 描述希望避免的元素，最多 500 字符，留空时省略                                               |
| `audio`           | `soundtrack` 或 `soundtrack_source` | 否   | 无                              | 一份 2 至 30 秒、最多 15 MB 的 WAV 或 MP3。上传或填写公开 URL。Atlas 也接受别名 `audio_url` |
| `resolution`      | `resolution`                        | 否   | `1080P`                         | 原生 `720P` 或 `1080P`。FlashVSR `1080P-SR` 或 `1440P-SR`                                   |
| `ratio`           | `ratio`                             | 否   | `16:9`                          | `16:9`、`9:16`、`1:1`、`4:3` 或 `3:4`                                                       |
| `duration`        | `duration`                          | 否   | 5                               | 2 至 15 秒的整数                                                                            |
| `prompt_extend`   | `prompt_extend`                     | 否   | true                            | 由模型扩写提示词                                                                            |
| `seed`            | `seed`                              | 否   | -1                              | 整数范围 -1 至 2147483647。-1 使用随机种子                                                  |

Atlas 模型说明补充了 `1080P-SR` 和 `1440P-SR` 的 API 值。选择这两项时，Atlas 在生成视频后使用 FlashVSR 放大。工作机使用规范字段 `audio` 传送配乐地址。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/text-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/text-to-video",
  "prompt": "镜头跟随海边小路上的自行车，拍下日落倒映在海面的光线。",
  "negative_prompt": "画面闪烁，字幕",
  "audio": "https://example.com/coast.wav",
  "resolution": "1080P-SR",
  "ratio": "16:9",
  "duration": 8,
  "prompt_extend": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、分辨率、比例和时长位于默认区。负面提示词、配乐、扩写开关和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
