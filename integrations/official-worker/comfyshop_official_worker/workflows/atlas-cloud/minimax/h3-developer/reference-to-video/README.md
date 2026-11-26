# MiniMax H3 Developer 参考生视频

根据文字和参考素材生成视频。使用参考图控制主体外观，参考视频提供动作和运镜，参考音频提供节奏。Atlas Cloud 模型 ID 为 `minimax/h3-developer/reference-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-developer/reference-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                                    | 输入约定                                                |
| ------------------ | ------------------------ | ---- | ----------------------------------------- | ------------------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-developer/reference-to-video` | 工作机从执行配置读取                                    |
| `prompt`           | `prompt`                 | 是   | 由用户填写                                | 描述主体、场景、动作和各素材的作用                      |
| `refers`           | 图片、视频和音频槽位     | 是   | 由用户上传                                | 1 至 12 个素材对象，至少包含一张参考图或一个参考视频    |
| `duration`         | `duration_seconds`       | 是   | `8`                                       | 4 至 15 秒的整数                                        |
| `resolution`       | `resolution`             | 是   | `768P`                                    | `480P`、`768P`、`1440p-sr`、`4k-sr`                     |
| `ratio`            | `aspect_ratio`           | 否   | `adaptive`                                | `adaptive`、`21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                                   | 是否在生成前扩写提示词                                  |

参考图槽位 `image_1` 至 `image_9` 支持 PNG、JPEG 和 WebP，视频槽位 `video_1` 至 `video_3` 支持 MP4 和 MOV，音频槽位 `audio_1` 至 `audio_3` 支持 WAV 和 MP3。工作机按图片、视频、音频和同组槽位编号的顺序生成数组，并跳过空槽。

每个对象需要公开的 `url`，`type` 的枚举为 `image`、`video`、`audio`。直接调用 API 时，如果 URL 带有可识别的扩展名，可以省略 `type`。工作机上传素材后显式写入 URL 和类型，提交前检查素材类型、总数及图片或视频要求。[素材上传](https://www.atlascloud.ai/docs/upload-files)

请求采用当前 Schema 和 HTTP 示例中的字段。静态示例数据还包含 `seed` 和 `num_inference_steps`，这两个字段的 Atlas 请求定义尚无文档说明。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-developer-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-developer-reference-to-video.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。素材地址为示例。

```json
{
  "model": "minimax/h3-developer/reference-to-video",
  "prompt": "保持参考图中纸风筝的外观，让它沿着视频中的运动轨迹升空。",
  "refers": [
    { "url": "https://example.com/kite.png", "type": "image" },
    { "url": "https://example.com/motion.mp4", "type": "video" }
  ],
  "duration": 8,
  "resolution": "768P",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 中读取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-developer/reference-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、每种素材的第一个槽位、时长、分辨率和比例位于默认区，剩余槽位和扩写位于高级区。维护账号可通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
