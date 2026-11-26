# Gemini 2.5 Flash 文生语音

Atlas Cloud 模型 ID 为 `google/gemini-2.5-flash-tts`。输入文字和预设音色后生成语音，也可以在文字中说明口音、语气或语速。[官方 API 与输入 Schema](https://www.atlascloud.ai/models/google/gemini-2.5-flash-tts)

## 参数

| ComfyShop 字段 | Atlas 参数 | 必填 | 初始值   | 说明                                                       |
| -------------- | ---------- | ---- | -------- | ---------------------------------------------------------- |
| 工作机配置     | `model`    | 是   | 模型 ID  | 从 `execution.config.model` 读取                           |
| `text`         | `text`     | 是   | 用户填写 | 要朗读的文本，可以附带自然语言指示。官方示例文字见接口定义 |
| `voice`        | `voice`    | 否   | `Kore`   | 工作流提供官方 30 种音色                                   |

## 请求与成品

工作机凭 `Authorization: Bearer <API_KEY>` 向 `POST https://api.atlascloud.ai/api/v1/model/generateAudio` 提交请求。示例使用默认音色。

```json
{
  "model": "google/gemini-2.5-flash-tts",
  "text": "用平和的语气朗读：今天的展览将在下午两点开始。",
  "voice": "Kore"
}
```

提交后读取 `data.id`，轮询 `GET /api/v1/model/prediction/{id}`。完成时从 `data.outputs` 下载音频并作为音频成品回传。语音可在结果中播放和下载。[官方音频文档](https://www.atlascloud.ai/docs/models/audio) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## 参数布局与译文

朗读文本和音色都在默认区。工作流标识为 `google-gemini-25-flash-tts`。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../docs/deployment.md#官方工作机)
