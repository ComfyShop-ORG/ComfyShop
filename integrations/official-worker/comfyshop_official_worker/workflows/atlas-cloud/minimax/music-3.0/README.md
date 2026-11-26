# MiniMax Music 3.0 音乐生成

根据描述和歌词生成歌曲或纯音乐。Atlas Cloud 模型 ID 为 `minimax/music-3.0`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/music-3.0)

## 官方参数

| Atlas 参数             | ComfyShop 字段           | 必填     | 默认值              | 输入约定                                              |
| ---------------------- | ------------------------ | -------- | ------------------- | ----------------------------------------------------- |
| `model`                | `execution.config.model` | 是       | `minimax/music-3.0` | 工作机从执行配置读取                                  |
| `prompt`               | `prompt`                 | 条件必填 | 空                  | 最多 2000 字符。纯音乐和自动写歌词时必填              |
| `lyrics`               | `lyrics`                 | 条件必填 | 空                  | 最多 3500 字符。手动撰写模式下必填                    |
| `is_instrumental`      | `instrumental`           | 否       | `false`             | 根据描述生成纯音乐                                    |
| `lyrics_optimizer`     | `automatic_lyrics`       | 否       | `false`             | 根据描述自动写歌词。使用时留空手写歌词                |
| `format`               | `format`                 | 否       | `mp3`               | `mp3`、`wav`、`pcm`                                   |
| `sample_rate`          | `sample_rate`            | 否       | 44100               | 16000、24000、32000、44100 Hz                         |
| `bitrate`              | `bitrate`                | 否       | 256000              | 仅用于 MP3，选项为 32000、64000、128000、256000 bit/s |
| `enable_sync_mode`     | `sync_mode`              | 否       | `false`             | 优先读取提交返回的成品                                |
| `enable_base64_output` | `base64_output`          | 否       | `false`             | 工作机解码音频并回传原件                              |

歌词每行一句，空行可用于停顿。段落标签单独成行，支持 `[Intro]`、`[Verse]`、`[Pre Chorus]`、`[Chorus]`、`[Post Chorus]`、`[Hook]`、`[Bridge]`、`[Interlude]`、`[Transition]`、`[Build Up]`、`[Break]`、`[Inst]`、`[Solo]`、`[Outro]`。选择纯音乐时，工作机提交音乐描述和音频设置。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-music-3.0.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-music-3.0.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/music-3.0",
  "prompt": "温暖的爵士三重奏，钢琴、低音提琴和轻柔鼓刷。",
  "is_instrumental": true,
  "format": "mp3",
  "sample_rate": 44100
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成时从 `data.outputs` 获取音频。同步模式可在提交响应中得到成品。选择 Base64 时工作机解码音频，PCM 以原文件下载。[调用示例](https://www.atlascloud.ai/models/minimax/music-3.0#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

音乐描述、歌词和生成模式位于默认区，音频格式、采样率、码率和返回方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
