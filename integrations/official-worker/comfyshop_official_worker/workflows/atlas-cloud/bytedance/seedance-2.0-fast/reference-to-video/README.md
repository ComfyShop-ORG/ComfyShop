# Seedance 2.0 Fast 参考生视频

使用参考图片、视频和音频生成、编辑或续写视频。 Atlas Cloud 模型 ID 为 `bytedance/seedance-2.0-fast/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                                              | 必填 | 默认值                                           | 输入约定                                                             |
| ------------------- | ----------------------------------------------------------- | ---- | ------------------------------------------------ | -------------------------------------------------------------------- |
| `model`             | `execution.config.model`                                    | 是   | `bytedance/seedance-2.0-fast/reference-to-video` | 工作机从执行配置读取                                                 |
| `prompt`            | `prompt`                                                    | 否   | 官方可编辑示例                                   | 可用 `@image1`、`@video1` 等按顺序引用素材                           |
| `reference_images`  | `reference_image_1` 至 `reference_image_9`，`image_sources` | 否   | —                                                | 最多 9 张，支持 URL、Base64、素材库引用或上传                        |
| `reference_videos`  | `reference_video_1` 至 `reference_video_3`，`video_sources` | 否   | —                                                | 最多 3 段，支持 URL、素材库引用或上传                                |
| `reference_audios`  | `reference_audio_1` 至 `reference_audio_3`，`audio_sources` | 否   | —                                                | 最多 3 段，支持 URL、Base64、素材库引用或上传。须搭配参考图或视频    |
| `duration`          | `duration_seconds`                                          | 否   | `5`                                              | 整数 4 至 15 或 `-1` 自动                                            |
| `ratio`             | `aspect_ratio`                                              | 否   | `adaptive`                                       | `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9` 或跟随主要参考素材的比例 |
| `resolution`        | `resolution`                                                | 否   | `720p`                                           | `480p`、`720p`、`720p-SR`、`1080p-SR`、`1440p-SR`                    |
| `bitrate_mode`      | `bitrate_mode`                                              | 否   | `standard`                                       | `standard` 或 `high`。高码率增大文件，Token 计费相同                 |
| `generate_audio`    | `generate_audio`                                            | 否   | `true`                                           | 生成同步音频                                                         |
| `seed`              | `seed`                                                      | 否   | `-1`                                             | 整数 `-1` 至 `4294967295`，`-1` 随机                                 |
| `watermark`         | `add_watermark`                                             | 否   | `false`                                          | 添加水印                                                             |
| `return_last_frame` | `include_last_frame`                                        | 否   | `false`                                          | 另存尾帧图片                                                         |

每种素材可以同时上传并提供多条外部来源，合计不超过该类的数量上限。每行输入一个来源，按上传槽位在前、外部来源在后的顺序编号。

- 参考图接受 JPEG、PNG、WebP、BMP、TIFF、GIF、HEIC 和 HEIF。单张小于 30 MB，宽高各 300–6,000 像素，宽高比 0.4–2.5。
- 参考视频接受 MP4 或 MOV，单段不超过 50 MB，长 2–15 秒，总时长不超过 15 秒。官方还要求 480p、720p 或 1080p，24–60 FPS，宽高各 300–6,000 像素，宽高比 0.4–2.5，总像素 409,600–2,086,876。
- 参考音频接受 WAV 或 MP3，单段不超过 15 MB，长 2–15 秒，总时长不超过 15 秒。使用音频需要至少一份参考图或参考视频。

工作机按已有素材元数据验证上传文件，外部 URL、Base64 和 `asset://<ASSET_ID>` 的时长及画面限制由 Atlas 校验。超过 ComfyShop 文本输入容量的 Base64 素材可直接上传。[素材库文档](https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video#asset-library-subject-reference-assets)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.0-fast-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-2.0-fast-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-2.0-fast-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-2.0-fast-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video#usage-examples)

```json
{
  "model": "bytedance/seedance-2.0-fast/reference-to-video",
  "prompt": "The character in image 1 dances gracefully to the music",
  "reference_images": ["https://example.com/character.png"],
  "reference_audios": ["https://example.com/music.wav"],
  "duration": 5,
  "ratio": "adaptive",
  "resolution": "720p",
  "bitrate_mode": "standard",
  "generate_audio": true,
  "seed": -1,
  "watermark": false,
  "return_last_frame": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的视频，以及开启 `return_last_frame` 后返回的尾帧图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、画面比例、分辨率和每种素材的第一个槽位。高级参数为其余素材槽位、外部来源、码率、音频、种子、水印和尾帧。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
