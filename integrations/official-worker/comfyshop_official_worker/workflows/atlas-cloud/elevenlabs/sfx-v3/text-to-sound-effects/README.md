# ElevenLabs SFX v3 音效生成

根据文字描述生成环境声、动作音效或可循环片段。Atlas Cloud 模型 ID 为 `elevenlabs/sfx-v3/text-to-sound-effects`。[模型 API 参考](https://www.atlascloud.ai/models/elevenlabs/sfx-v3/text-to-sound-effects)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                                    | 输入约定                                     |
| ------------------ | ------------------------ | ---- | ----------------------------------------- | -------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `elevenlabs/sfx-v3/text-to-sound-effects` | 工作机从执行配置读取                         |
| `prompt`           | `prompt`                 | 是   | 官方示例文本                              | 1 至 2000 字符                               |
| `duration`         | `duration`               | 否   | 5                                         | 1 至 30 秒的整数                             |
| `loop`             | `loop`                   | 否   | `false`                                   | 生成可无缝循环的声音                         |
| `prompt_influence` | `prompt_influence`       | 否   | 0.3                                       | 0 至 1，越高越贴合描述                       |
| `output_format`    | `format`                 | 否   | `mp3`                                     | `mp3` 为 44.1 kHz、128 kbps，`wav` 为 48 kHz |

[官方 Schema](https://static.atlascloud.ai/model/schema/elevenlabs-sfx-v3-text-to-sound-effects.json) · [官方示例数据](https://static.atlascloud.ai/model/example/elevenlabs-sfx-v3-text-to-sound-effects.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "elevenlabs/sfx-v3/text-to-sound-effects",
  "prompt": "Steady rain tapping against an attic window",
  "duration": 8,
  "loop": true,
  "prompt_influence": 0.5,
  "output_format": "wav"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。[官方调用示例](https://www.atlascloud.ai/models/elevenlabs/sfx-v3/text-to-sound-effects#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

描述、时长和输出格式位于默认区，循环和描述影响力位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
