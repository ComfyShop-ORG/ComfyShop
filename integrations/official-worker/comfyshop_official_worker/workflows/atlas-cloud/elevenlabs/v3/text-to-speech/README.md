# ElevenLabs v3 文本转语音

将文本合成为语音。Atlas Cloud 模型 ID 为 `elevenlabs/v3/text-to-speech`。[官方接口文档](https://www.atlascloud.ai/docs/more-models/elevenlabs/v3-text-to-speech/generateAudio) · [模型系列](https://www.atlascloud.ai/models/elevenlabs)

## 官方参数

| Atlas 参数                 | ComfyShop 字段           | 必填 | 默认值                         | 输入约定                                                 |
| -------------------------- | ------------------------ | ---- | ------------------------------ | -------------------------------------------------------- |
| `model`                    | `execution.config.model` | 是   | `elevenlabs/v3/text-to-speech` | 工作机从执行配置读取                                     |
| `text`                     | `text`                   | 是   | 用户填写                       | 1 至 5000 字符                                           |
| `voice`                    | `voice`                  | 否   | Bella 的音色 ID                | 选择下表任一预设                                         |
| `language_code`            | `language`               | 否   | `null`                         | 留空由供应商推断。填写时按所选音色的 Schema 语言代码校验 |
| `stability`                | `stability`              | 否   | 0.5                            | 0 至 1                                                   |
| `apply_text_normalization` | `normalization`          | 否   | `auto`                         | `auto` 自动判断，`on` 开启，`off` 关闭                   |

表单展示音色名称和语言，执行时使用 Schema 中的音色 ID。静态示例数据的音色使用名称，可参考它的音频输出。[官方 Schema](https://static.atlascloud.ai/model/schema/elevenlabs-v3-text-to-speech.json) · [官方示例数据](https://static.atlascloud.ai/model/example/elevenlabs-v3-text-to-speech.json)

## 预设音色

| 名称    | 音色 ID                | Schema 语言代码 | 官方试听                                                                    |
| ------- | ---------------------- | --------------- | --------------------------------------------------------------------------- |
| Bella   | `hpp4J3VqNfWAUOO0d1Us` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_bella.mp3)   |
| Roger   | `CwhRBWXzGAHq8TQ4Fs17` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_roger.mp3)   |
| Sarah   | `EXAVITQu4vr4xnSDxMaL` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_sarah.mp3)   |
| Laura   | `FGY2WhTYpPnrIDTdsKH5` | `fr`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_laura.mp3)   |
| Charlie | `IKne3meq5aSn9XLyUdCD` | `zh`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_charlie.mp3) |
| George  | `JBFqnCBsd6RMkjVDRZzb` | `ja`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_george.mp3)  |
| Callum  | `N2lVS1w4EtoT3dr4eOWO` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_callum.mp3)  |
| River   | `SAz9YHcvj6GT2YYXdXww` | `zh`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_river.mp3)   |
| Harry   | `SOYHLrjzK2X1ezoPC6cr` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_harry.mp3)   |
| Liam    | `TX3LPaxmHKxFdv7VOQHJ` | `de`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_liam.mp3)    |
| Alice   | `Xb7hH8MSUJpSbSDYk0k2` | `ja`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_alice.mp3)   |
| Matilda | `XrExE9yKIg1WjnnlVkGX` | `it`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_matilda.mp3) |
| Will    | `bIHbv24MWmeRgasZH58o` | `es`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_will.mp3)    |
| Jessica | `cgSgspJ2msm6clMCkdW9` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_jessica.mp3) |
| Eric    | `cjVigY5qzO86Huf0OWal` | `fr`            | [试听](https://static.atlascloud.ai/media/audios/voice_preview_eric.mp3)    |
| Chris   | `iP95p4xoKVk53GoZ742B` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_chris.mp3)   |
| Brian   | `nPczCjzI2devNBz1zQrb` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_brian.mp3)   |
| Daniel  | `onwK4e9ZLuTAKqWW03F9` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_daniel.mp3)  |
| Lily    | `pFZP5JQG7iQjIQuC4Bku` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_lily.mp3)    |
| Adam    | `pNInz6obpgDQGcFmaJgB` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_adam.mp3)    |
| Bill    | `pqHfZKP75CvOlQylNhV4` | `en-US`         | [试听](https://static.atlascloud.ai/media/audios/voice_preview_bill.mp3)    |

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "elevenlabs/v3/text-to-speech",
  "text": "欢迎收听今晚的故事。",
  "voice": "IKne3meq5aSn9XLyUdCD",
  "language_code": "zh",
  "stability": 0.5,
  "apply_text_normalization": "auto"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，完成后从 `data.outputs` 下载音频。[官方请求示例](https://www.atlascloud.ai/docs/more-models/elevenlabs/v3-text-to-speech/generateAudio) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

文本、音色和语言位于默认区，稳定性和文本规范化位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
