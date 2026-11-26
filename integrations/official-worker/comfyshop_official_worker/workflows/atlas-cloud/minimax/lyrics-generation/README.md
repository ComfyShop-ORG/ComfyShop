# MiniMax 歌词生成

根据主题撰写新歌词，也可修改或续写已有歌词。Atlas Cloud 模型 ID 为 `minimax/lyrics-generation`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/lyrics-generation)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填     | 默认值                      | 输入约定                                    |
| ------------------ | ------------------------ | -------- | --------------------------- | ------------------------------------------- |
| `model`            | `execution.config.model` | 是       | `minimax/lyrics-generation` | 工作机从执行配置读取                        |
| `mode`             | `mode`                   | 是       | `write_full_song`           | `write_full_song` 写新歌，`edit` 修改或续写 |
| `prompt`           | `prompt`                 | 是       | 空                          | 最多 2000 字符。提交空字符串时随机生成      |
| `lyrics`           | `lyrics`                 | 条件必填 | 空                          | `edit` 模式填写现有歌词，最多 3500 字符     |
| `title`            | `title`                  | 否       | 空                          | 保留指定歌名                                |
| `enable_sync_mode` | `sync_mode`              | 否       | `false`                     | 优先使用提交响应中的成品                    |

现有歌词每行一句。支持 `[Intro]`、`[Verse]`、`[Pre Chorus]`、`[Chorus]`、`[Post Chorus]`、`[Hook]`、`[Bridge]`、`[Interlude]`、`[Transition]`、`[Build Up]`、`[Break]`、`[Inst]`、`[Solo]`、`[Outro]` 等独立段落标签。写新歌时，工作机省略原歌词字段。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-lyrics-generation.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-lyrics-generation.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/lyrics-generation",
  "mode": "write_full_song",
  "prompt": "写一首关于夜班结束后走回家的民谣。",
  "title": "最后一盏路灯"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机从 `data.lyrics_result.lyrics` 或 `data.outputs` 读取歌词正文，保存为文本。结构化结果另存为 JSON，可包含歌名、风格标签和歌词。歌词文本可用于 MiniMax Music 工作流。[官方调用示例](https://www.atlascloud.ai/models/minimax/lyrics-generation#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

生成模式、主题和原歌词位于默认区，歌名和返回方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
