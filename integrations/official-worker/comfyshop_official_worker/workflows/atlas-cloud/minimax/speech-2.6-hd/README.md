# MiniMax Speech 2.6 HD 文本转语音

合成高保真语音，适用于旁白与长文本朗读。Atlas Cloud 模型 ID 为 `minimax/speech-2.6-hd`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/speech-2.6-hd)

## 官方参数

| Atlas 参数       | ComfyShop 字段           | 必填 | 默认值                        | 输入约定                                       |
| ---------------- | ------------------------ | ---- | ----------------------------- | ---------------------------------------------- |
| `model`          | `execution.config.model` | 是   | `minimax/speech-2.6-hd`       | 工作机从执行配置读取                           |
| `text`           | `text`                   | 是   | 官方示例文本                  | 最多 10000 字符                                |
| `voice`          | `voice`                  | 否   | `English_expressive_narrator` | 从 Schema 中的 15 个系统音色选取               |
| `language_boost` | `language`               | 否   | `auto`                        | 自动检测或选择语言提示，`Chinese,Yue` 表示粤语 |
| `speed`          | `speed`                  | 否   | 1                             | 0.5 至 2                                       |
| `vol`            | `volume`                 | 否   | 1                             | 0 至 10                                        |
| `pitch`          | `pitch`                  | 否   | 0                             | -12 至 12 的整数                               |
| `emotion`        | `emotion`                | 否   | `auto`                        | 自动推断或选择九种情绪和语气                   |
| `format`         | `format`                 | 否   | `mp3`                         | `mp3`、`wav`、`flac`                           |
| `sample_rate`    | `sample_rate`            | 否   | 32000                         | 8000、16000、22050、24000、32000、44100 Hz     |
| `bitrate`        | `bitrate`                | 否   | 128000                        | 32000、64000、128000、256000 bit/s             |

当前 Schema 和页面调用示例使用 `voice`。静态示例数据中的音色键为 `voice_id`。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-speech-2.6-hd.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-speech-2.6-hd.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/speech-2.6-hd",
  "text": "Welcome to today's reading.",
  "voice": "English_expressive_narrator",
  "language_boost": "English",
  "format": "mp3"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。[官方调用示例](https://www.atlascloud.ai/models/minimax/speech-2.6-hd#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

朗读文本、音色和语言提示位于默认区，其余选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
