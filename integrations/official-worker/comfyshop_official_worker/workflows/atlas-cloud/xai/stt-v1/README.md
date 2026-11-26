# xAI STT v1 语音转文字

转写音频或视频的音轨，可按词返回时间戳和说话人信息。Atlas Cloud 模型 ID 为 `xai/stt-v1`。[模型 API 参考](https://www.atlascloud.ai/models/xai/stt-v1)

## 官方参数

| Atlas 参数           | ComfyShop 字段           | 必填     | 默认值       | 输入约定                                                    |
| -------------------- | ------------------------ | -------- | ------------ | ----------------------------------------------------------- |
| `model`              | `execution.config.model` | 是       | `xai/stt-v1` | 工作机从执行配置读取                                        |
| `audio`              | `source_audio`           | 是       | 用户上传     | 可绑定音频或含音轨的视频。供应商最大 500 MB                 |
| `text_normalization` | `normalize_numbers`      | 否       | `false`      | 转换口述数字、货币和单位，开启后需要选择语言                |
| `language`           | `language`               | 条件必填 | 自动识别     | 工作流使用 Atlas Schema 中的 25 个语言代码                  |
| `keyterm`            | `key_terms`              | 否       | `[]`         | 每行一项，上限 100 项，每项最多 50 字符                     |
| `diarize`            | `diarize`                | 否       | `false`      | 标记词语所属说话人                                          |
| `filler_words`       | `keep_fillers`           | 否       | `false`      | 保留语气词和停顿词                                          |
| `audio_format`       | `audio_format`           | 否       | `auto`       | 容器自动识别，裸音频选择 `pcm`、`mulaw` 或 `alaw`           |
| `sample_rate`        | `sample_rate`            | 条件必填 | 省略         | 裸音频必填。可选 8000、16000、22050、24000、44100、48000 Hz |
| `multichannel`       | `multichannel`           | 否       | `false`      | 独立转写各声道                                              |
| `channels`           | `channels`               | 条件必填 | 省略         | 裸音频分声道转写时填写，2 至 8                              |
| `enable_sync_mode`   | `sync_mode`              | 否       | `false`      | 优先从提交响应读取结果                                      |

工作机上传素材并发送 URL。直接调用可使用公开 URL 或 Base64 编码音频。平台单次素材上传默认上限为 256 MiB。带容器的文件可使用 MP3、WAV、M4A、FLAC、OGG、Opus、AAC、MP4、MKV 等。裸音频需按照实际编码使用 `.raw` 或 `.pcm`、`.mulaw` 或 `.ulaw`、`.alaw`。[官方 Schema](https://static.atlascloud.ai/model/schema/xai-stt-v1.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-stt-v1.json) · [xAI 原生格式参考](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。录音地址为示例。

```json
{
  "model": "xai/stt-v1",
  "audio": "https://example.com/recording.mp3",
  "language": "en",
  "text_normalization": true,
  "keyterm": ["ComfyShop"],
  "diarize": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机将转写正文保存为 UTF-8 文本，将 `data.stt_result` 保存为 JSON。结构化结果可包含词语时间戳、说话人和分声道结果。开启同步模式时，工作机在保存生成编号后处理当次响应里的成品。[官方调用示例](https://www.atlascloud.ai/models/xai/stt-v1#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

素材、语言、数字规范化和热词位于默认区。说话人、保留口头语、裸音频参数、分声道和同步开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
