# MiniMax Music 2.6 音乐生成

根据风格描述生成带人声的歌曲或纯音乐。Atlas Cloud 模型 ID 为 `minimax/music-2.6`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/music-2.6)

## 官方参数

| Atlas 参数        | ComfyShop 字段           | 必填 | 默认值               | 输入约定                           |
| ----------------- | ------------------------ | ---- | -------------------- | ---------------------------------- |
| `model`           | `execution.config.model` | 是   | `minimax/music-2.6`  | 工作机从执行配置读取               |
| `prompt`          | `prompt`                 | 是   | 官方风格示例         | 最多 2000 字符                     |
| `lyrics`          | `lyrics`                 | 否   | 表单提供原创分段示例 | 最多 3500 字符                     |
| `is_instrumental` | `instrumental`           | 否   | `false`              | 根据描述生成纯音乐，工作机省略歌词 |
| `format`          | `format`                 | 否   | `mp3`                | `mp3`、`wav`、`pcm`                |
| `sample_rate`     | `sample_rate`            | 否   | 44100                | 16000、24000、32000、44100 Hz      |
| `bitrate`         | `bitrate`                | 否   | 256000               | 32000、64000、128000、256000 bit/s |

歌词每行一句，空行可用于停顿。段落标签单独成行，支持 `[Intro]`、`[Verse]`、`[Pre Chorus]`、`[Chorus]`、`[Bridge]`、`[Outro]`、`[Inst]`。表单提供一段原创示例歌词。Atlas 默认歌词见原始 Schema。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-music-2.6.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-music-2.6.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/music-2.6",
  "prompt": "安静的夜间爵士，电钢琴和鼓刷，82 BPM。",
  "is_instrumental": true,
  "format": "mp3",
  "sample_rate": 44100,
  "bitrate": 256000
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载音频。PCM 以原文件下载。[官方调用示例](https://www.atlascloud.ai/models/minimax/music-2.6#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

音乐描述、歌词、纯音乐开关位于默认区，音频格式、采样率和码率位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
