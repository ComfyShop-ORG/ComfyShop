# Seedance 2.5 Flash 参考生视频

Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5-flash/reference-to-video`。模型可从参考素材生成视频，也可编辑或延长一段视频。[官方 API 与输入 Schema](https://www.atlascloud.ai/models/bytedance/seedance-2.5-flash/reference-to-video)

## 参数

| ComfyShop 字段          | Atlas 参数                 | 必填 | 初始值     | 约定                                                         |
| ----------------------- | -------------------------- | ---- | ---------- | ------------------------------------------------------------ |
| 工作机配置              | `model`                    | 是   | 模型 ID    | 从 `execution.config.model` 读取                             |
| `image_1` 至 `image_10` | `reference_images`         | 否   | 空         | 最多 10 张图片                                               |
| `video_1` 至 `video_5`  | `reference_videos`         | 否   | 空         | 最多 5 段视频                                                |
| `audio_1` 至 `audio_5`  | `reference_audios`         | 否   | 空         | 最多 5 段音频                                                |
| `prompt`                | `prompt`                   | 否   | 空         | 按实际提交顺序引用 `@Image1`、`@Video1`、`@Audio1`           |
| `duration_seconds`      | `duration`                 | 否   | `5`        | 4–30 秒的整数，`-1` 为自动                                   |
| `aspect_ratio`          | `ratio`                    | 否   | `adaptive` | 可选 `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9`、`adaptive` |
| `resolution`            | `resolution`               | 否   | `720p`     | `480p` 或 `720p`                                             |
| `reference_task_type`   | `omni_reference_task_type` | 否   | 自动       | 可选 `auto`、`reference`、`edit`、`extend`                   |
| `generate_audio`        | `generate_audio`           | 否   | `true`     | 生成与画面同步的声音                                         |
| `add_watermark`         | `watermark`                | 否   | `false`    | 添加水印                                                     |
| `include_last_frame`    | `return_last_frame`        | 否   | `false`    | 单独交付尾帧图片                                             |
| `video_format`          | `output_format`            | 否   | `mp4`      | `mp4` 或 `mov`                                               |

工作机按编号上传已填槽位并生成三个独立的 URL 数组。空槽会跳过。例如只上传第 2 和第 5 张图时，提示词用 `@Image1` 和 `@Image2`。省略 `prompt` 时，Atlas 使用默认提示词 `The character in image 1 dances gracefully to the music`。[素材上传文档](https://www.atlascloud.ai/docs/upload-files)

- 图片从 ComfyShop 上传时支持 PNG、JPEG、WebP 或 GIF。Atlas 要求宽高各 300–6000 像素、宽高比 0.4–2.5、每张小于 30 MB。
- 视频使用 MP4 或 MOV。Atlas 接收 H.264 或 H.265 视频和 AAC 或 MP3 音轨。单段 2–30 秒、全部参考视频合计最多 30 秒，宽高各 300–6000 像素，像素数 409600–8295044，宽高比 0.4–2.5，帧率 24–60 fps，单段最多 200 MB。
- 音频使用 WAV 或 MP3。单段 2–30 秒、全部参考音频合计最多 30 秒，单段最多 15 MB。可以只提供音频作为参考。

省略任务类型时由 Atlas 根据提示词及素材判断。使用显式类型时须提供参考素材。选择 `edit` 时上传一个 4–30 秒的视频并设置 `adaptive` 与 `-1`。选择 `extend` 时上传一个视频并设置 `adaptive`。提示词应与所选类型一致。[任务类型说明](https://www.atlascloud.ai/models/bytedance/seedance-2.5-flash/reference-to-video)

## 请求和成品

工作机凭 `Authorization: Bearer <API_KEY>` 调用 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。下面的示例使用一张参考图和一段参考音频。

```json
{
  "model": "bytedance/seedance-2.5-flash/reference-to-video",
  "reference_images": ["https://example.com/subject.png"],
  "reference_audios": ["https://example.com/music.wav"],
  "prompt": "让 @Image1 中的纸风车随着 @Audio1 的节奏转动。",
  "omni_reference_task_type": "reference",
  "duration": 5,
  "resolution": "720p",
  "ratio": "adaptive",
  "return_last_frame": true
}
```

提交后保存 `data.id`，调用 `GET /api/v1/model/prediction/{id}` 续查。任务完成时下载 `data.outputs` 中的视频和可选尾帧图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## 参数布局与译文

每类素材的第一个上传槽和主要生成参数在默认区。其余槽位、任务类型及输出设置在高级区。工作流标识为 `seedance-25-flash-reference-to-video`。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../../docs/deployment.md#官方工作机)
