# Seedance 2.5 参考生视频

使用图像、视频或音频作为参考，生成、编辑或延长视频，也可生成 480p 草稿。 Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-2.5/reference-to-video)

## Atlas 接口参数

| Atlas 参数                 | ComfyShop 字段                                               | 必填 | 默认值                                      | 输入约定                                                                                                                              |
| -------------------------- | ------------------------------------------------------------ | ---- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                    | `execution.config.model`                                     | 是   | `bytedance/seedance-2.5/reference-to-video` | 工作机从执行配置读取                                                                                                                  |
| `reference_images`         | `reference_image_1` 至 `reference_image_30`，`image_sources` | 否   | —                                           | 最多 30 张，支持 URL、Base64、素材库引用或上传                                                                                        |
| `reference_videos`         | `reference_video_1` 至 `reference_video_10`，`video_sources` | 否   | —                                           | 最多 10 段，支持 URL、素材库引用或上传                                                                                                |
| `reference_audios`         | `reference_audio_1` 至 `reference_audio_10`，`audio_sources` | 否   | —                                           | 最多 10 段，支持 URL、Base64、素材库引用或上传。可单独参考音频                                                                        |
| `prompt`                   | `prompt`                                                     | 否   | 官方可编辑示例                              | 可用 `@Image1`、`@Video1` 等按顺序引用素材                                                                                            |
| `duration`                 | `duration_seconds`                                           | 否   | `5`                                         | 整数 4 至 30 或 `-1` 自动                                                                                                             |
| `resolution`               | `resolution`                                                 | 否   | `720p`                                      | `480p`、`720p`、`720p-sr`、`720p-esr`、`1080p`、`1080p-sr`、`1080p-esr`、`1080p-esr & 60fps`、`1440p-sr`、`1440p-esr`、`4k-esr`、`4k` |
| `ratio`                    | `aspect_ratio`                                               | 否   | `adaptive`                                  | `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9` 或根据主要参考素材自适应                                                                  |
| `output_format`            | `video_format`                                               | 否   | `mp4`                                       | `mp4` 或 `mov`。MOV 使用 YUV 4:4:4                                                                                                    |
| `generate_audio`           | `generate_audio`                                             | 否   | `true`                                      | 生成同步音频                                                                                                                          |
| `watermark`                | `add_watermark`                                              | 否   | `false`                                     | 添加水印                                                                                                                              |
| `return_last_frame`        | `include_last_frame`                                         | 否   | `false`                                     | 另存尾帧图片                                                                                                                          |
| `draft`                    | `draft`                                                      | 否   | `false`                                     | 开启时生成 480p 预览并返回草稿 ID                                                                                                     |
| `omni_reference_task_type` | `omni_reference_task_type`                                   | 否   | 留空时 `auto`                               | `auto`、`reference`、`edit` 或 `extend`                                                                                               |

每种素材按上传槽位在前、外部来源在后的顺序编号。图像和音频的外部来源接受公开 URL、Base64 或 `asset://<ASSET_ID>`，视频接受公开 URL 或素材库引用，每行一个来源。超过 ComfyShop 文本输入容量的 Base64 素材可直接上传。[素材库文档](https://www.atlascloud.ai/models/bytedance/seedance-2.5/reference-to-video#asset-library-subject-reference-assets)

- 参考图最多 30 张，接受 JPEG、PNG、WebP、BMP、TIFF、GIF、HEIC 或 HEIF。单张小于 30 MB，宽高各 300–6,000 像素，宽高比 0.4–2.5。
- 参考视频最多 10 段，每段 2–30 秒，合计不超过 30 秒。接受 480p 至 4K、H.264/H.265 视频及 AAC/MP3 音轨的 MP4 或 MOV。帧率 24–60，宽高各 300–6,000 像素，宽高比 0.4–2.5，总像素 409,600–8,295,044，单段不超过 200 MB。
- 参考音频最多 10 段，接受 WAV 或 MP3，单段不超过 15 MB、长 2–30 秒，合计不超过 30 秒。可仅使用音频素材。

本地上传的素材按已有文件元数据校验。外部来源的尺寸、时长、编解码器和帧率由 Atlas 验证。使用 `@Image1`、`@Video1`、`@Audio1` 等引用对应类型的第一个素材。

`omni_reference_task_type` 留空时由模型推断。显式 `reference` 用于参考生成，`edit` 需恰好一段 4–30 秒的视频、`duration: -1` 和 `ratio: "adaptive"`，`extend` 需恰好一段视频和 `ratio: "adaptive"`。显式值需要参考素材。无论是否指定任务类型，提示词请求编辑原视频时都应选 `-1` 并保留原视频比例。Atlas 校验选定模式与提示词、素材数量和长度的匹配情况。

`720p-sr` / `720p-esr` 基于原生 480p。`1080p-sr` / `1080p-esr` / `1080p-esr & 60fps` 基于原生 720p。`1440p-sr` / `1440p-esr` / `4k-esr` 基于原生 1080p，`4k-esr` 将短边增强至 2160 像素。不同原生与增强档位可有不同价格。

开启 `draft` 后，Atlas 以 480p 生成预览并按 480p 计费，覆盖请求分辨率。结果包含草稿 ID，七天内可用该 ID 生成 1080p 或 4K 正式版。[草稿转正式版](https://www.atlascloud.ai/models/bytedance/seedance-2.5/draft-complete)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.5-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-2.5-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-2.5-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-2.5-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-2.5/reference-to-video#usage-examples)

```json
{
  "model": "bytedance/seedance-2.5/reference-to-video",
  "prompt": "The character in image 1 dances gracefully to the music",
  "reference_images": ["https://example.com/character.png"],
  "reference_audios": ["https://example.com/music.wav"],
  "duration": 5,
  "resolution": "720p",
  "ratio": "adaptive",
  "output_format": "mp4",
  "generate_audio": true,
  "watermark": false,
  "return_last_frame": false,
  "draft": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的视频和可选尾帧。开启 `draft` 时另存仅含草稿 ID 的 TXT，可将其中的 ID 填入草稿转正式版工作流。若完成响应省略 `data.draft_id`，使用草稿的预测 ID。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、画面比例、分辨率和每种素材的第一个槽位。高级参数为其余素材槽位、外部来源、同步音频、水印、尾帧、视频容器、草稿模式和任务类型提示。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
