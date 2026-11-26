# Qwen Audio 3.1 TTS Flash 文本转语音

低延迟合成多语言及方言语音，可通过指令控制风格。Atlas Cloud 模型 ID 为 `alibaba/qwen-audio-3.1-tts-flash/text-to-speech`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/qwen-audio-3.1-tts-flash/text-to-speech)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段            | 必填 | 默认值                                            | 输入约定                                                              |
| ---------------- | ------------------------- | ---- | ------------------------------------------------- | --------------------------------------------------------------------- |
| `model`          | `execution.config.model`  | 是   | `alibaba/qwen-audio-3.1-tts-flash/text-to-speech` | 工作机从执行配置读取                                                  |
| `text`           | `text`                    | 是   | 官方示例文本                                      | 要合成的文本，启用 SSML 时支持 SSML 和 LaTeX                          |
| `voice`          | `voice` 或 `custom_voice` | 是   | `longanhuan_v3.1`                                 | 70 个新加坡系统音色，或填写当前模型可用的音色 ID                      |
| `output_format`  | `output_format`           | 否   | `mp3`                                             | MP3、裸 PCM、WAV、Opus                                                |
| `sample_rate`    | `sample_rate`             | 否   | 22050                                             | 8000、12000、16000、22050、24000、44100、48000 Hz                     |
| `speed`          | `speed`                   | 否   | 1                                                 | 0.5 至 2 倍                                                           |
| `pitch`          | `pitch`                   | 否   | 1                                                 | 0.5 至 2 倍                                                           |
| `volume`         | `volume`                  | 否   | 50                                                | 0 至 100                                                              |
| `bit_rate`       | `bit_rate`                | 否   | 供应商选择                                        | Opus 码率，单位 kbps                                                  |
| `language_hints` | `language_hint`           | 否   | 留空                                              | 选一个代码后发送单项数组。支持 zh、en、ja、ko、fr、de、pt、it、vi、id |
| `instruction`    | `instruction`             | 否   | 空字符串                                          | 用自然语言指定情绪、语气、角色或方言                                  |
| `enable_ssml`    | `enable_ssml`             | 否   | false                                             | 开启 SSML 解析                                                        |
| `seed`           | `seed`                    | 否   | -1                                                | -1 为随机，或指定 0 至 65535                                          |

高级区的已有音色 ID 填写后优先生效。方言可通过风格指令指定，例如「请讲上海话」。表单按 Atlas 当前 Schema 设置种子默认值为 `-1`，官方示例使用 `0`。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-qwen-audio-3.1-tts-flash-text-to-speech.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-qwen-audio-3.1-tts-flash-text-to-speech.json) · [阿里云音色列表](https://docs.modelstudio.console.alibabacloud.com/zh/model-studio/qwen-audio-tts-voice-list)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "alibaba/qwen-audio-3.1-tts-flash/text-to-speech",
  "text": "侬好，今朝天气蛮好。",
  "voice": "longanlingxin_v3.1",
  "language_hints": ["zh"],
  "instruction": "请用上海话，以自然的聊天语气朗读。",
  "output_format": "mp3",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。[官方调用示例](https://www.atlascloud.ai/models/alibaba/qwen-audio-3.1-tts-flash/text-to-speech#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

默认区提供朗读文本、音色和风格指令。高级区提供已有音色 ID、语言提示、音频格式与参数、SSML 和种子。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
