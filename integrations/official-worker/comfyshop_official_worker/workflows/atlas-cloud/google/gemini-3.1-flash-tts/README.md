# Gemini 3.1 Flash 文生语音

选择一个预设音色，用自然语言提示语气、口音与节奏。Atlas Cloud 模型 ID 为 `google/gemini-3.1-flash-tts`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-3.1-flash-tts)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段           | 必填 | 默认值                        | 输入约定                                     |
| ---------- | ------------------------ | ---- | ----------------------------- | -------------------------------------------- |
| `model`    | `execution.config.model` | 是   | `google/gemini-3.1-flash-tts` | 工作机从执行配置读取                         |
| `text`     | `text`                   | 是   | 官方示例文本                  | 最多 10000 字符，可在文本中给出朗读指示      |
| `voice`    | `voice`                  | 否   | `Kore`                        | 选择 Atlas Schema 中的 30 种 Google 预设音色 |

端点文档和 Schema 使用 `voice`。官方静态示例和模型说明使用 `voice_name`，模型说明还标出了 10000 字符限制。工作机按当前端点定义提交 `voice`。[端点文档](https://www.atlascloud.ai/docs/zh/more-models/google/gemini-3.1-flash-tts/generateAudio) · [官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-3.1-flash-tts.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-3.1-flash-tts.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-3.1-flash-tts.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "google/gemini-3.1-flash-tts",
  "text": "请以轻快的语气朗读：周六的手作市集将在上午十点开门。",
  "voice": "Leda"
}
```

取预测编号 `id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从预测的 `outputs` 下载 WAV 成品。工作机支持文档里的预测对象以及通用接口的 `data` 包装。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

朗读文本和音色位于默认区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
