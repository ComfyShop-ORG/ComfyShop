# Gemini 2.5 Pro 文生语音

将文本转为语音，可选择预设音色，在文本内描述朗读风格、口音、语气或语速。Atlas Cloud 模型 ID 为 `google/gemini-2.5-pro-tts`。[模型 API 参考](https://www.atlascloud.ai/models/google/gemini-2.5-pro-tts)

## 官方参数

| Atlas 参数 | ComfyShop 字段           | 必填 | 默认值                      | 输入约定                                                 |
| ---------- | ------------------------ | ---- | --------------------------- | -------------------------------------------------------- |
| `model`    | `execution.config.model` | 是   | `google/gemini-2.5-pro-tts` | 工作机从执行配置读取                                     |
| `text`     | `text`                   | 是   | 由用户填写                  | 要合成的文字和朗读指示。模型说明列出的上限为 10,000 字符 |
| `voice`    | `voice`                  | 否   | `Kore`                      | 提供官方 30 种音色                                       |

ComfyShop 将必填朗读文本留空。官方 Schema 中提供了演示文本、完整音色枚举及各音色试听地址。请求采用 Schema 和 HTTP 示例中的 `voice` 键。静态示例数据使用 `voice_name` 键。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-2.5-pro-tts.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-2.5-pro-tts.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "google/gemini-2.5-pro-tts",
  "text": "请用舒缓的语气朗读。这一段步道沿着湖岸，全程约两公里。",
  "voice": "Kore"
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，下载 `data.outputs` 的 WAV 成品。工作机回传原音频，可在 ComfyShop 播放和下载。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-2.5-pro-tts#usage-examples) · [音频文档](https://www.atlascloud.ai/docs/models/audio) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

朗读文本和音色在默认区，维护账号可通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
