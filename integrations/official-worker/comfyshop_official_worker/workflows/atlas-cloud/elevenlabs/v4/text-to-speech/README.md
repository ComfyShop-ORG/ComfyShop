# ElevenLabs v4 文本转语音

合成单人语音或多音色对话。Atlas Cloud 模型 ID 为 `elevenlabs/v4/text-to-speech`。[模型 API 参考](https://www.atlascloud.ai/models/elevenlabs/v4/text-to-speech)

## 官方参数

| Atlas 参数                 | ComfyShop 字段            | 必填     | 默认值                         | 输入约定                                                                    |
| -------------------------- | ------------------------- | -------- | ------------------------------ | --------------------------------------------------------------------------- |
| `model`                    | `execution.config.model`  | 是       | `elevenlabs/v4/text-to-speech` | 工作机从执行配置读取                                                        |
| `text`                     | `text`                    | 条件必填 | 官方示例文本                   | 单人朗读使用，最多 10000 字符。支持 `[cheerfully]`、`[whispers]` 等表达标签 |
| `voice`                    | `voice` 或 `custom_voice` | 否       | `Roger`                        | 官方预设或已有的 ElevenLabs 音色 ID                                         |
| `output_format`            | `format`                  | 否       | `mp3_44100_128`                | 支持表单列出的 MP3、Opus、PCM、WAV、μ-law 和 A-law 格式                     |
| `stability`                | `stability`               | 否       | 0.5                            | 0 至 1                                                                      |
| `similarity_boost`         | `similarity`              | 否       | 0.75                           | 0 至 1                                                                      |
| `clone_strength`           | `clone_strength`          | 否       | 供应商选择                     | 专业复刻音色可设置 0 至 1                                                   |
| `language_code`            | `language`                | 否       | `null`                         | ISO 639-1 语言代码                                                          |
| `apply_text_normalization` | `normalization`           | 否       | `auto`                         | `auto`、`on`、`off`                                                         |
| `seed`                     | `seed`                    | 否       | 随机                           | 0 至 4294967295 的整数                                                      |
| `inputs`                   | `dialogue`                | 否       | `[]`                           | 对话 JSON 数组。每项包含 `text`，可选 `voice`                               |

对话按数组顺序生成，最多 10 种音色，台词合计最多 10000 字符。未指定音色的台词使用顶层音色。供应商建议请求总文本控制在 2000 字符以内，以便在上游合成时间内完成。[官方 Schema](https://static.atlascloud.ai/model/schema/elevenlabs-v4-text-to-speech.json) · [官方示例数据](https://static.atlascloud.ai/model/example/elevenlabs-v4-text-to-speech.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "elevenlabs/v4/text-to-speech",
  "voice": "Roger",
  "inputs": [
    { "text": "[cheerfully] 欢迎来到录音室。" },
    { "text": "我们准备开始了吗？", "voice": "Bella" }
  ],
  "output_format": "mp3_44100_128"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。PCM、μ-law、A-law 保留为裸音频原件。[官方调用示例](https://www.atlascloud.ai/models/elevenlabs/v4/text-to-speech#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

朗读文本、预设音色和输出格式位于默认区。自定义音色、对话和其余设置位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
