# xAI TTS v1 文本转语音

把文字合成为带停顿、轻声、笑声等表达的音频。Atlas Cloud 模型 ID 为 `xai/tts-v1`。[官方模型 API](https://www.atlascloud.ai/models/xai/tts-v1)

## Atlas 接口参数

| Atlas 参数                   | ComfyShop 字段               | 必填 | 默认值       | 输入约定                                                  |
| ---------------------------- | ---------------------------- | ---- | ------------ | --------------------------------------------------------- |
| `model`                      | `execution.config.model`     | 是   | `xai/tts-v1` | 工作机从执行配置读取                                      |
| `text`                       | `text`                       | 是   | 无           | 1 至 15000 字符，支持单点标签与成对标签                   |
| `language`                   | `language`                   | 是   | `auto`       | 自动检测，或选择官方 Schema 支持的 20 个语言代码          |
| `voice_id`                   | `voice_id`                   | 否   | `eve`        | 表单包含 Atlas Schema 的 71 个音色                        |
| `codec`                      | `codec`                      | 否   | `mp3`        | `mp3`、`wav`、`pcm`、`mulaw`、`alaw`                      |
| `sample_rate`                | `sample_rate`                | 否   | 24000        | 8000、16000、22050、24000、44100、48000 Hz                |
| `bit_rate`                   | `bit_rate`                   | 否   | 128000       | 仅 MP3 使用，支持 32000、64000、96000、128000、192000 bps |
| `speed`                      | `speed`                      | 否   | 1            | 0.7 至 1.5 倍                                             |
| `text_normalization`         | `text_normalization`         | 否   | false        | 转换数字、缩写与符号后再朗读                              |
| `optimize_streaming_latency` | `optimize_streaming_latency` | 否   | 0            | 0 为最佳音质，1 为低延迟，2 为最低延迟                    |

对 Schema 明确要求语言的音色使用自动检测时，工作机填入所需语言。手动指定时须与要求相符。比如 Jian 对应 `zh`，Sakura 对应 `ja`，多语种音色 Eve 可以使用 `auto`。完整的音色试听、语言关系和标签列表见 Atlas Schema。[官方 Schema](https://static.atlascloud.ai/model/schema/xai-tts-v1.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-tts-v1.json) · [xAI 原生接口](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "xai/tts-v1",
  "text": "现在开始录音。[pause] <whisper>说轻一点。</whisper>",
  "language": "zh",
  "voice_id": "jpi39icg",
  "codec": "mp3",
  "sample_rate": 24000
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。PCM、μ-law 与 A-law 保留为裸音频原件。[官方调用示例](https://www.atlascloud.ai/models/xai/tts-v1#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

朗读文本、音色和语言位于默认区，其余设置位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
