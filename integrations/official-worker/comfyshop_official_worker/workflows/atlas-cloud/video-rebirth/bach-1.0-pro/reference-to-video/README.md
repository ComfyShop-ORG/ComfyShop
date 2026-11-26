# Bach 1.0 Pro 参考生视频

用参考图、视频和音频引导生成 5 至 16 秒的视频。 Atlas Cloud 模型 ID 为 `video-rebirth/bach-1.0-pro/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                              | 必填           | 默认值                                                            | 输入约定                                                                                                   |
| ------------------ | ----------------------------------------------------------- | -------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                                    | 是             | `video-rebirth/bach-1.0-pro/reference-to-video`                   | 工作机从执行配置读取                                                                                       |
| `prompt`           | `prompt`                                                    | 是             | `Use @Video1 as motion reference and @Audio1 as audio reference.` | 最多 6,500 字符，按素材类型和顺序引用 `@Image1`、`@Video1`、`@Audio1`                                      |
| `reference_images` | `reference_image_1` 至 `reference_image_9`、`image_sources` | 与视频至少一项 | —                                                                 | 至多 9 项。JPEG、PNG 或 WebP，每张 ≤10 MB，每边 320–6,000 px，宽高比 1:4 至 4:1                            |
| `reference_videos` | `reference_video_1` 至 `reference_video_3`、`video_sources` | 与图至少一项   | —                                                                 | 至多 3 项。H.264/H.265 MP4 或 MOV，每段 ≤30 MB、2–15 秒，合计 ≤15 秒。每边 320–6,000 px，宽高比 1:4 至 4:1 |
| `reference_audios` | `reference_audio_1` 至 `reference_audio_3`、`audio_sources` | 否             | —                                                                 | 至多 3 项。WAV 或 MP3，每段 ≤15 MB、2–15 秒，合计 ≤15 秒                                                   |
| `duration`         | `duration`                                                  | 否             | `5`                                                               | 5 至 16 秒的整数                                                                                           |
| `resolution`       | `resolution`                                                | 否             | `1080p`                                                           | `1080p` 或 `4k`                                                                                            |
| `aspect_ratio`     | `aspect_ratio`                                              | 否             | `16:9`                                                            | `16:9`、`9:16`、`4:3`、`3:4`、`21:9`、`1:1`                                                                |
| `generate_audio`   | `generate_audio`                                            | 否             | `true`                                                            | 关闭后输出静音视频                                                                                         |
| `seed`             | `seed`                                                      | 否             | 随机                                                              | 1 至 100,000 的整数                                                                                        |

三种来源合计最多 12 项，其中至少一张图片或一段视频。工作机将同类型上传文件按槽位顺序发送，再追加来源文本中的素材。视频与音频经 Atlas 素材上传接口换取 HTTPS 地址，手动来源也需为公开 HTTPS。图片来源可以是公开 URL、Base64 数据 URI 或原始 Base64。工作机按已保存的上传素材属性校验文件、画面尺寸和时长，Atlas 校验视频编码和远程素材。

[官方 Schema](https://static.atlascloud.ai/model/schema/video-rebirth-bach-1.0-pro-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/video-rebirth-bach-1.0-pro-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/video-rebirth-bach-1.0-pro-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/reference-to-video#usage-examples)

```json
{
  "model": "video-rebirth/bach-1.0-pro/reference-to-video",
  "prompt": "Use @Video1 as motion reference and @Audio1 as audio reference.",
  "reference_videos": [
    "https://static.atlascloud.ai/media/videos/1e55e58d6984a5318f8f99c075aad7c4.mp4"
  ],
  "reference_audios": ["https://static.atlascloud.ai/model/example/bytedance-seed-audio-1.0.mp3"],
  "duration": 5
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词、每类第一份素材、时长、分辨率与宽高比。高级参数包括后续素材、外部来源、音频开关和随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
