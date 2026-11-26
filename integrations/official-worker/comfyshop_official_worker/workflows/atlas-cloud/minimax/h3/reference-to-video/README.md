# MiniMax H3 参考生视频

用参考图、视频或音频和提示词生成视频，保留主体外观并控制动作与节奏。 Atlas Cloud 模型 ID 为 `minimax/h3/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/minimax/h3/reference-to-video)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                                                | 必填 | 默认值                          | 输入约定                                                       |
| ------------------ | ----------------------------------------------------------------------------- | ---- | ------------------------------- | -------------------------------------------------------------- |
| `model`            | `execution.config.model`                                                      | 是   | `minimax/h3/reference-to-video` | 工作机从执行配置读取                                           |
| `prompt`           | `prompt`                                                                      | 是   | —                               | 描述视频画面、动作和镜头                                       |
| `refers`           | `image_1`–`image_9`、`video_1`–`video_3`、`audio_1`–`audio_3` 与三类 URL 字段 | 是   | —                               | 对象数组，每项有 `url` 和可选 `type`。图片、视频和音频可以混用 |
| `duration`         | `duration_seconds`                                                            | 是   | `8`                             | 整数 4 至 15 秒                                                |
| `resolution`       | `resolution`                                                                  | 是   | `2K`                            | `480P`、`768P`、`2K`、`1080p-esr`、`1440p-esr`、`4k-esr`       |
| `ratio`            | `aspect_ratio`                                                                | 否   | `adaptive`                      | `adaptive`、`21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16`        |
| `prompt_expansion` | `expand_prompt`                                                               | 否   | `false`                         | 使用 H3 Context-IR 扩写，按 Token 另行计费                     |

参考素材总数最多 12 项，至少一张图或一段视频。公开 HTTPS URL 须直达素材文件，每行一个。工作机按素材类别设置 `type`，把上传槽位放在外部来源之前。直接使用 Atlas API 时 `type` 可省略，由接口根据 URL 扩展名推断。

- 图片最多 9 张，可用 JPEG、PNG、WebP、HEIC、HEIF。每张不超过 30 MB，宽高各 256–5,760 像素，宽高比 0.4–2.5。
- 视频最多 3 段，可用 MP4、MOV。单段 2–15 秒、最多 50 MB，合计不超过 15 秒。宽高各 256–5,760 像素，宽高比 0.4–2.5，23.976–60 fps。视频为 H.264/AVC 或 H.265/HEVC，音轨为 AAC 或 MP3。
- 音频最多 3 段，可用 WAV、MP3。单段 2–15 秒、最多 15 MB，合计不超过 15 秒。

已上传的文件按元数据校验，外部 URL 与编解码器、帧率由 Atlas 校验。原生分辨率为 480P、768P、2K，ESR 档位由原生 768P 增强。

模型说明中的 `callback_url` 属于 MiniMax 原生接口的状态回调。Atlas 网关另有通用 webhook，内置工作机沿用预测轮询。[Atlas Webhooks](https://www.atlascloud.ai/docs/webhooks)

[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/minimax-h3-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/minimax/h3-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/minimax/h3/reference-to-video#usage-examples)

```json
{
  "model": "minimax/h3/reference-to-video",
  "prompt": "让镜头沿着参考画面中的街道平稳前进，保留环境声。",
  "refers": [
    {
      "url": "https://example.com/street.png",
      "type": "image"
    },
    {
      "url": "https://example.com/ambient.wav",
      "type": "audio"
    }
  ],
  "duration": 8,
  "resolution": "2K",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、每类素材的第一个槽位、时长、比例和分辨率。高级参数为其余素材槽位、外部 URL 和提示词扩写。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
