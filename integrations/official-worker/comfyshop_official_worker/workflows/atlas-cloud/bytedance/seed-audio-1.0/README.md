# Seed Audio 1.0 文本生成音频

根据脚本生成旁白、场景音效和背景声。Atlas Cloud 模型 ID 为 `bytedance/seed-audio-1.0`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seed-audio-1.0)

## 官方参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                     | 输入约定                                                                |
| --------------- | ------------------------ | ---- | -------------------------- | ----------------------------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `bytedance/seed-audio-1.0` | 工作机从执行配置读取                                                    |
| `text`          | `text`                   | 是   | 官方示例提示词             | 最多 3000 字符，可按 `@Audio1`、`@Audio2`、`@Audio3` 引用相应音频或音色 |
| `references`    | 音色、音频和图片槽       | 否   | 省略                       | 至多三项音频或音色参考，或一张图片                                      |
| `format`        | `format`                 | 否   | `mp3`                      | `mp3`、`wav`、`pcm`、`ogg_opus`                                         |
| `sample_rate`   | `sample_rate`            | 否   | `24000`                    | 8000、16000、24000、32000、44100 和 48000 Hz                            |
| `pitch_rate`    | `pitch`                  | 否   | `0`                        | -12 至 12                                                               |
| `speech_rate`   | `speech_rate`            | 否   | `0`                        | -50 至 100，分别对应 0.5 倍至 2 倍                                      |
| `loudness_rate` | `loudness`               | 否   | `0`                        | -50 至 100，分别对应 0.5 倍至 2 倍                                      |

每个参考对象只能设置一种来源。按填写顺序提交有效项。参考图片须单独使用。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seed-audio-1.0.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seed-audio-1.0.json) · [BytePlus 参数和参考素材限制](https://docs.byteplus.com/en/docs/byteplusvoice/seedaudio-01)

| 参考对象属性 | 表单映射                                    |
| ------------ | ------------------------------------------- |
| `speaker`    | 选择预设音色或填写实际已注册的自定义音色 ID |
| `audio_url`  | 上传参考音频，工作机取得链接                |
| `audio_data` | 开启该音频槽的内联开关，由工作机生成 Base64 |
| `image_url`  | 上传图片，工作机取得链接                    |
| `image_data` | 开启图片的内联开关，由工作机生成 Base64     |

每段音频最多 30 秒和 10 MB，格式为 MP3、WAV、PCM 或 OGG Opus。参考图最多 10 MB，支持 JPEG、PNG 或 WebP。

## 预设音色

| ID                                       | 官方试听                                                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `zh_female_vv_uranus_bigtts`             | [Vivi 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_vv_uranus_bigtts.mp3)                     |
| `zh_female_xiaohe_uranus_bigtts`         | [Xiaohe 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_xiaohe_uranus_bigtts.mp3)               |
| `zh_male_m191_uranus_bigtts`             | [Yunzhou 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_male_m191_uranus_bigtts.mp3)                  |
| `zh_male_taocheng_uranus_bigtts`         | [Xiaotian 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_male_taocheng_uranus_bigtts.mp3)             |
| `zh_male_liufei_uranus_bigtts`           | [Liufei 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_male_liufei_uranus_bigtts.mp3)                 |
| `zh_female_sophie_uranus_bigtts`         | [Sophie 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_sophie_uranus_bigtts.mp3)               |
| `zh_female_qingxinnvsheng_uranus_bigtts` | [Fresh Female 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_qingxinnvsheng_uranus_bigtts.mp3) |
| `zh_female_cancan_uranus_bigtts`         | [Cancan 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_cancan_uranus_bigtts.mp3)               |
| `zh_female_tianmeitaozi_uranus_bigtts`   | [Sweet Peach 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_female_tianmeitaozi_uranus_bigtts.mp3)    |
| `zh_male_ruyayichen_uranus_bigtts`       | [Yichen 2.0](https://static.atlascloud.ai/model/example/seed-audio/voices/zh_male_ruyayichen_uranus_bigtts.mp3)             |

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seed-audio-1.0",
  "text": "一阵轻柔的铃声响起。@Audio1 说，欢迎收听今天的节目。",
  "references": [{ "speaker": "zh_female_vv_uranus_bigtts" }],
  "format": "mp3",
  "sample_rate": 24000
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 下载音频。PCM 原件可下载并按所选采样率使用。[调用示例](https://www.atlascloud.ai/models/bytedance/seed-audio-1.0#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

脚本和输出格式位于默认区，采样率、音频调整和可选参考素材位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
