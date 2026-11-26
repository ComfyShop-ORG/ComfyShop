# LTX 2.3 Pro 音频生成视频

用音频生成同步视频，可配首尾帧和提示词。720p 或 1080p 最长 20 秒。 Atlas Cloud 模型 ID 为 `ltx/ltx-2.3-pro/audio-to-video`。[官方模型 API](https://www.atlascloud.ai/models/ltx/ltx-2.3-pro/audio-to-video)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                            | 必填 | 默认值                           | 输入约定                                                                                            |
| --------------- | ----------------------------------------- | ---- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`                  | 是   | `ltx/ltx-2.3-pro/audio-to-video` | 工作机从执行配置读取                                                                                |
| `audio`         | `driving_audio` 或 `driving_audio_source` | 是   | —                                | 720p／1080p 最长 20 秒，1440p／4K 最长 10 秒。上传、URL、Base64 或 `asset://`                       |
| `image`         | `first_frame` 或 `first_frame_source`     | 条件 | —                                | 提示词为空时须提供首帧，上传、URL、Base64 或 `asset://`                                             |
| `last_image`    | `last_frame` 或 `last_frame_source`       | 否   | —                                | 尾帧和首帧一起使用，支持相同来源                                                                    |
| `prompt`        | `prompt`                                  | 条件 | Schema 提供可编辑示例            | 首帧为空时须提供提示词                                                                              |
| `resolution`    | `resolution`                              | 否   | `1080p`                          | `720p`、`1080p`、`1440p`、`4k`。选择自动时省略字段                                                  |
| `aspect_ratio`  | `aspect_ratio`                            | 否   | `16:9`                           | `16:9` 横向或 `9:16` 竖向                                                                           |
| `fps`           | `fps`                                     | 否   | `24`                             | `24`、`25`、`48`、`50`                                                                              |
| `camera_motion` | `camera_motion`                           | 否   | —                                | `dolly_in`、`dolly_out`、`dolly_left`、`dolly_right`、`jib_up`、`jib_down`、`static`、`focus_shift` |

音频时长决定视频时长。720p、1080p 支持最多 20 秒。1440p、4K 支持最多 10 秒。选择自动分辨率时，由 Atlas 根据选出的分辨率确认时长。支持 MP3、M4A、OGG。WAV 仅接受封装 AAC-LC、MP3、Vorbis 或 FLAC 的文件，编码由 Atlas 校验。首尾帧支持 JPEG、PNG、WebP。空分辨率交由 Atlas 推断。帧率采用 Atlas Schema 的枚举。[LTX 原生输入格式](https://docs.ltx.io/input-formats/)

[官方 Schema](https://static.atlascloud.ai/model/schema/ltx-ltx-2.3-pro-audio-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/ltx-ltx-2.3-pro-audio-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/ltx-ltx-2.3-pro-audio-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/ltx/ltx-2.3-pro/audio-to-video#usage-examples)

```json
{
  "model": "ltx/ltx-2.3-pro/audio-to-video",
  "audio": "https://example.com/voice.m4a",
  "image": "https://example.com/first.png",
  "prompt": "人物说话时自然眨眼。",
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "fps": 24
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为驱动音频、首尾帧、提示词、分辨率和宽高比。高级参数为帧率、镜头运动及媒体来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
