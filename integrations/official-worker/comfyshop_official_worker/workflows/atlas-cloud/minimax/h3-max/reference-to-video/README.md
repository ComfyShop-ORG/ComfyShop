# MiniMax H3 Max 参考生视频

根据提示词和参考素材生成视频。参考图可用于保持主体外观，视频可提供动作和运镜，音频可提供节奏。Atlas Cloud 模型 ID 为 `minimax/h3-max/reference-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-max/reference-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                              | 输入约定                                                |
| ------------------ | ------------------------ | ---- | ----------------------------------- | ------------------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-max/reference-to-video` | 工作机从执行配置读取                                    |
| `prompt`           | `prompt`                 | 是   | 由用户填写                          | 描述场景、动作和各素材的作用                            |
| `refers`           | 图片、视频和音频槽位     | 是   | 由用户上传                          | 1 至 12 个对象，至少包含一张图片或一个视频              |
| `duration`         | `duration_seconds`       | 是   | `8`                                 | 5 至 15 秒的整数                                        |
| `resolution`       | `resolution`             | 是   | `768P`                              | `480P`、`768P`                                          |
| `ratio`            | `aspect_ratio`           | 否   | `adaptive`                          | `adaptive`、`21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                             | 是否在生成前扩写提示词                                  |

每个 `refers` 对象包含必填的公开 `url` 和选填的 `type`，枚举为 `image`、`video`、`audio`。工作机从用户上传的素材得到 URL，按图片、视频、音频和同组槽位编号的顺序构建数组，跳过空槽，并显式发送素材类型。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-max-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-max-reference-to-video.json) · [素材上传文档](https://www.atlascloud.ai/docs/upload-files)

| 素材 | 槽位                   | 格式与约定                                                                                                                           |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 图片 | `image_1` 至 `image_9` | ComfyShop 接收 JPEG、PNG、WebP。官方要求每边 256 至 5760 像素、宽高比 0.4 至 2.5、单张最多 30 MB。直接调用 Atlas 还可使用 HEIC、HEIF |
| 视频 | `video_1` 至 `video_3` | MP4 或 MOV，H.264 或 H.265，23.976 至 60 fps。单段 2 至 15 秒且最多 50 MB，合计最多 15 秒                                            |
| 音频 | `audio_1` 至 `audio_3` | WAV 或 MP3。单段 2 至 15 秒且最多 15 MB，合计最多 15 秒                                                                              |

工作机在提交前检查素材类型、总数及图片或视频要求。尺寸、编码、大小和时长按供应商的素材要求准备。

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。素材地址为示例。

```json
{
  "model": "minimax/h3-max/reference-to-video",
  "prompt": "保持图片中的白色帆船，参考视频中的镜头运动，沿着湖面推进。",
  "refers": [
    { "url": "https://example.com/sailboat.png", "type": "image" },
    { "url": "https://example.com/camera.mp4", "type": "video" }
  ],
  "resolution": "768P",
  "duration": 8,
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 获取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-max/reference-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

每种素材的第一个槽位、提示词、时长、分辨率和比例位于默认区。剩余槽位与提示词扩写位于高级区。维护账号可通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
