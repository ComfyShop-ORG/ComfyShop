# Suno Chirp v6 音乐生成

根据歌曲描述生成两个演绎版本。也可以提供自定义歌词、风格与时长。Atlas Cloud 模型 ID 为 `suno/chirp-v6`。[官方模型 API](https://www.atlascloud.ai/models/suno/chirp-v6)

## Atlas 接口参数

工作流字段和 Atlas 参数同名。工作机从 `execution.config.model` 读取必填的 `model`。

| Atlas 参数             | 必填     | 默认值       | 输入约定                                                                         |
| ---------------------- | -------- | ------------ | -------------------------------------------------------------------------------- |
| `prompt`               | 条件必填 | 官方示例描述 | 灵感模式填曲风、情绪等描述，自定义模式填歌词。最多 3000 字符。自定义纯音乐可留空 |
| `custom`               | 否       | false        | 开启自定义模式，使用歌词和附加风格设置                                           |
| `instrumental`         | 否       | false        | 开启后生成纯乐器演奏                                                             |
| `variety`              | 否       | 供应商选择   | 两种模式都支持，选 `off`、`normal`、`high`、`extra` 或 `max`                     |
| `vocal_gender`         | 否       | 供应商选择   | 两种模式都支持，选 `Male` 或 `Female`                                            |
| `title`                | 否       | 供应商选择   | 歌曲标题，最多 200 字符                                                          |
| `style`                | 否       | 供应商选择   | 风格标签，最多 500 字符                                                          |
| `duration`             | 否       | 供应商选择   | 目标 10 至 360 秒，实际成品可略有浮动                                            |
| `negative_tags`        | 否       | 供应商选择   | 排除的风格，最多 500 字符                                                        |
| `auto_lyrics`          | 否       | false        | 允许模型改写歌词                                                                 |
| `style_weight`         | 否       | 供应商选择   | 风格遵循程度，0 至 1                                                             |
| `weirdness_constraint` | 否       | 供应商选择   | 创意程度，0 至 1                                                                 |
| `audio_weight`         | 否       | 供应商选择   | 参考音频权重，0 至 1                                                             |
| `persona_id`           | 否       | 无           | 已有的声音角色 ID                                                                |

从 `title` 到 `persona_id` 的设置仅在自定义模式下发送。未选择的选项、不适用的字段和空白文字会省略。[官方 Schema](https://static.atlascloud.ai/model/schema/suno-chirp-v6.json) · [官方示例数据](https://static.atlascloud.ai/model/example/suno-chirp-v6.json) · [模型说明](https://static.atlascloud.ai/model/readme/suno-chirp-v6.md)

## API 调用

将以下自定义纯音乐示例发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "suno/chirp-v6",
  "custom": true,
  "instrumental": true,
  "title": "雨过天晴",
  "style": "轻爵士钢琴、原声贝斯、温暖",
  "duration": 60,
  "variety": "normal"
}
```

用响应的预测编号轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后，工作机下载 `outputs` 中的两个音乐版本，并把 `thumbnail` 返回的歌曲封面保存为本次生成的图片成品。[官方调用示例](https://www.atlascloud.ai/models/suno/chirp-v6#usage-examples) · [官方音频文档](https://www.atlascloud.ai/docs/models/audio) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

歌曲描述或歌词、自定义模式和纯音乐位于默认区。声音、风格、时长及其他选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
