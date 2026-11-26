# Wan 3.0 Prime 参考生视频

以参考图、视频或音频引导新视频，可用文档或网页补充上下文。 Atlas Cloud 模型 ID 为 `alibaba/wan-3.0-prime/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/reference-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                                                                                                                                    | 必填 | 默认值                                     | 输入约定                                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `model`           | `execution.config.model`                                                                                                                          | 是   | `alibaba/wan-3.0-prime/reference-to-video` | 工作机从执行配置读取                                                                                        |
| `prompt`          | `prompt`                                                                                                                                          | 是   | 无                                         | 描述目标场景、动作与镜头，最多 20,000 字符                                                                  |
| `refers`          | `reference_image_1` 至 `reference_image_10`、`reference_video_1` 至 `reference_video_5`、`reference_audio_1` 至 `reference_audio_5`及各组地址字段 | 否   | 无                                         | 最多 20 个参考对象，允许混合素材类型                                                                        |
| `refers[].url`    | 上传素材或该类素材的地址                                                                                                                          | 是   | 无                                         | 公开素材 URL。上传文件由工作机转换成 Atlas 地址                                                             |
| `refers[].type`   | 素材所属槽位                                                                                                                                      | 否   | 按 URL 推断                                | `image`、`video` 或 `audio`。工作机按槽位填入类型                                                           |
| `resolution`      | `resolution`                                                                                                                                      | 否   | `1080p`                                    | 原生 `480p`、`720p`、`1080p`。ESR `720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr`                            |
| `duration`        | `duration`                                                                                                                                        | 否   | 5                                          | 2 至 30 秒，`-1` 为自动时长                                                                                 |
| `ratio`           | `ratio`                                                                                                                                           | 否   | `adaptive`                                 | `adaptive`、`16:9`、`4:3`、`1:1`、`3:4` 或 `9:16`                                                           |
| `audio`           | `audio`                                                                                                                                           | 否   | true                                       | 控制是否生成音轨                                                                                            |
| `enable_thinking` | `enable_thinking`                                                                                                                                 | 否   | true                                       | 文档或网页解析依赖此开关                                                                                    |
| `file`            | `file`                                                                                                                                            | 否   | 无                                         | 公开文档 URL，支持 DOCX、DOC、XLSX、XLS、PPTX、PPT、PDF、TXT、KEY、PAGES、NUMBERS、MD。最多 100 MB 和 50 页 |
| `link`            | `link`                                                                                                                                            | 否   | 无                                         | 无需登录的公开网页 URL，与 `file` 二选一                                                                    |
| `seed`            | `seed`                                                                                                                                            | 否   | 由模型决定                                 | 整数。`-1` 使用随机种子，留空时省略                                                                         |

图片最多十张。JPEG、无透明通道的 PNG、BMP 或 WebP，每边 240 至 8000 像素，长短边比例最多 8:1，每张最多 20 MB。视频最多五段，MP4 或 MOV，每边 240 至 4096 像素，每段 1 至 15 秒并且最多 100 MB。音频最多五段，WAV 或 MP3，每段 1 至 15 秒并且最多 15 MB。视频与音频各组时长分别最多 15 秒。工作机先排列上传素材，再按类别追加各行地址，校验上传原件。Atlas 校验公开地址的实际格式和用量。README 对必填参考素材、提示词长度及思考默认值另有说明，工作流采用当前 API 参数页及 Schema 的定义。关闭深度思考会省略 `file` 和 `link`。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-3.0-prime-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-3.0-prime-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-3.0-prime-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-3.0-prime-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/reference-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-3.0-prime/reference-to-video",
  "prompt": "让参考图中的纸船沿着水流漂动，跟随参考片段的运镜和参考音频的节奏。",
  "refers": [
    {
      "url": "https://example.com/paper-boat.jpg",
      "type": "image"
    },
    {
      "url": "https://example.com/camera.mp4",
      "type": "video"
    },
    {
      "url": "https://example.com/beat.wav",
      "type": "audio"
    }
  ],
  "resolution": "1080p",
  "duration": 5,
  "ratio": "16:9",
  "audio": true,
  "enable_thinking": true,
  "file": "https://example.com/storyboard.pdf"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首个各类素材槽位、分辨率、时长及比例位于默认区。其余素材槽位、素材地址、音频、深度思考、文档、网页与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
