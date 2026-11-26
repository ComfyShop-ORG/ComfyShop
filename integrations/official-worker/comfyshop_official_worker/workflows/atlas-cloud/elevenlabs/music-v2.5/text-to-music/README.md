# ElevenLabs Music v2.5 文本生成音乐

根据音乐描述或分段方案生成歌曲，输出 48 kHz、192 kbps 的 MP3。Atlas Cloud 模型 ID 为 `elevenlabs/music-v2.5/text-to-music`。[模型 API 参考](https://www.atlascloud.ai/models/elevenlabs/music-v2.5/text-to-music)

## 官方参数

| Atlas 参数           | ComfyShop 字段           | 必填     | 默认值                                | 输入约定                                                      |
| -------------------- | ------------------------ | -------- | ------------------------------------- | ------------------------------------------------------------- |
| `model`              | `execution.config.model` | 是       | `elevenlabs/music-v2.5/text-to-music` | 工作机从执行配置读取                                          |
| `prompt`             | `prompt`                 | 条件必填 | 官方描述示例                          | 描述模式需要 1 至 2000 字符                                   |
| `duration`           | `duration`               | 条件必填 | 30                                    | 3 至 600 秒的整数。有分段方案时填写方案总时长向上取整后的秒数 |
| `force_instrumental` | `instrumental`           | 否       | `false`                               | 描述模式可开启。使用分段方案时工作机省略此参数                |
| `composition_plan`   | `composition_plan`       | 条件必填 | 省略                                  | 分段模式填写包含 `chunks` 的 JSON 对象                        |

方案中的 `chunks` 为 1 至 30 个对象，单段 `duration_ms` 为 3000 至 120000 毫秒，总时长为 3 至 600 秒。`text` 必填，最多 30 行且每行最多 200 字符。首行可用方括号标记段名，歌词可用花括号附带演奏指示。`positive_styles` 至少有一个字符串。`negative_styles` 可选。`context_adherence` 可选 `low`、`medium`、`high`，供应商默认 `high`。[官方 Schema](https://static.atlascloud.ai/model/schema/elevenlabs-music-v2.5-text-to-music.json) · [官方示例数据](https://static.atlascloud.ai/model/example/elevenlabs-music-v2.5-text-to-music.json)

## API 调用

将以下通用示例作为 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "elevenlabs/music-v2.5/text-to-music",
  "duration": 15,
  "composition_plan": {
    "chunks": [
      {
        "text": "[Intro]\n{Soft electric piano and brushed drums}",
        "duration_ms": 15000,
        "positive_styles": ["lo-fi jazz", "electric piano"],
        "negative_styles": ["distorted guitar"],
        "context_adherence": "high"
      }
    ]
  }
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，完成后从 `data.outputs` 下载 MP3。[官方调用示例](https://www.atlascloud.ai/models/elevenlabs/music-v2.5/text-to-music#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

音乐描述、时长和纯音乐开关位于默认区。分段方案位于高级区，可粘贴 Detailed 模型返回的 `composition_plan` 对象。使用方案时清空描述并关闭纯音乐开关。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
