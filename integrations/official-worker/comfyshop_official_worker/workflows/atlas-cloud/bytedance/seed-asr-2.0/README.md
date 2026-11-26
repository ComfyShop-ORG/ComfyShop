# Seed ASR 2.0 语音转文字

将录音转写成文字，可为片段附上时间戳和说话人。Atlas Cloud 模型 ID 为 `bytedance/seed-asr-2.0`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seed-asr-2.0)

## 官方参数

| Atlas 参数            | ComfyShop 字段           | 必填 | 默认值                   | 输入约定                                              |
| --------------------- | ------------------------ | ---- | ------------------------ | ----------------------------------------------------- |
| `model`               | `execution.config.model` | 是   | `bytedance/seed-asr-2.0` | 工作机从执行配置读取                                  |
| `audio_url`           | `audio`                  | 是   | 用户上传                 | MP3、WAV、OGG 或原始 PCM                              |
| `format`              | `format`                 | 否   | `mp3`                    | `mp3`、`wav`、`ogg`、`raw`，与文件格式一致            |
| `language`            | `language`               | 否   | 自动识别                 | 留空识别中英文和支持的方言，也可指定语言代码          |
| `enable_itn`          | `normalize_numbers`      | 否   | `true`                   | 将口述数字和单位转为常用书写形式                      |
| `enable_punc`         | `punctuation`            | 否   | `false`                  | 添加标点                                              |
| `enable_ddc`          | `remove_fillers`         | 否   | `false`                  | 去除口头语与重复                                      |
| `enable_speaker_info` | `speaker_labels`         | 否   | `false`                  | 区分最多 10 位说话人                                  |
| `show_utterances`     | `timestamps`             | 否   | `false`                  | 返回带起止时间的片段                                  |
| `context`             | `hotwords`               | 否   | 省略                     | JSON 字符串，使用 `hotwords` 数组传入含 `word` 的对象 |
| `boosting_table_name` | `boosting_table`         | 否   | 省略                     | 已在 Atlas Cloud 配置的热词表名称                     |
| `correct_table_name`  | `correction_table`       | 否   | 省略                     | 已在 Atlas Cloud 配置的纠错表名称                     |

工作机将录音上传到 Atlas Cloud 获得 URL。直接调用也可使用公开 URL 或 Base64。原始 PCM 使用 16 kHz 单声道 16 位小端格式，文件名以 `.raw` 或 `.pcm` 结尾。平台单次素材上传默认上限为 256 MiB，Atlas 模型文档的输入上限约为 512 MB。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seed-asr-2.0.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seed-asr-2.0.json) · [素材上传接口](https://www.atlascloud.ai/docs/upload-files) · [BytePlus 录音识别文档](https://docs.byteplus.com/en/docs/byteplusvoice/asraudiofile)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。音频地址为示例。

```json
{
  "model": "bytedance/seed-asr-2.0",
  "audio_url": "https://example.com/recording.mp3",
  "format": "mp3",
  "enable_punc": true,
  "show_utterances": true,
  "context": "{\"hotwords\":[{\"word\":\"ComfyShop\"}]}"
}
```

用 `data.id` 轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机将 `data.outputs[0]` 中的转写正文保存为 UTF-8 文本。当响应含 `data.stt_result` 时，执行同时保留包含时间戳、说话人等信息的 JSON。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seed-asr-2.0#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

音频、格式、语言和标点位于默认区。转写规则、时间戳和词表位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
