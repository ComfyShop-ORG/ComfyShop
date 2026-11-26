# MiniMax H3 Fast 参考生视频

用提示词和参考素材生成 480P 视频。图像提供主体外观，视频提供动作和运镜，音频提供节奏。Atlas Cloud 模型 ID 为 `minimax/h3-fast/reference-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-fast/reference-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                    |
| ------------------ | ------------------------ | ---- | ------------------------------------ | ------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-fast/reference-to-video` | 工作机从执行配置读取                        |
| `prompt`           | `prompt`                 | 是   | 由用户填写                           | 描述场景、动作和各素材的作用                |
| `refers`           | 图片、视频和音频槽位     | 是   | 由用户上传                           | 1 至 12 个对象，至少包含一张图片或一个视频  |
| `duration`         | `duration_seconds`       | 是   | `8`                                  | 5 至 15 秒的整数                            |
| `resolution`       | `resolution`             | 是   | `480P`                               | 唯一枚举为 `480P`                           |
| `ratio`            | `aspect_ratio`           | 否   | `16:9`                               | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                              | 是否在生成前扩写提示词                      |

`refers` 的每个对象需要一个公开的素材 `url`，可带 `type`，枚举为 `image`、`video`、`audio`。工作机上传素材并显式带上类型，按图片、视频、音频和同组槽位号的顺序组装数组，跳过空槽。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-fast-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-fast-reference-to-video.json)

| 素材 | 槽位                   | 格式与约定                                                                                                                          |
| ---- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 图片 | `image_1` 至 `image_9` | JPEG、PNG、WebP。单张最多 30 MB，每边 256 至 5760 像素，宽高比 0.4 至 2.5                                                           |
| 视频 | `video_1` 至 `video_3` | MP4 或 MOV，H.264 或 H.265，23.976 至 60 fps。每边 256 至 5760 像素，宽高比 0.4 至 2.5。单段 2 至 15 秒且最多 50 MB，合计最多 15 秒 |
| 音频 | `audio_1` 至 `audio_3` | WAV 或 MP3。单段 2 至 15 秒且最多 15 MB，合计最多 15 秒                                                                             |

工作机校验素材类型、总数及图片或视频要求。视频内音轨使用 AAC 或 MP3。其余素材规则见模型说明。[参考素材说明](https://static.atlascloud.ai/model/readme/minimax-h3-fast-reference-to-video.md) · [素材上传文档](https://www.atlascloud.ai/docs/upload-files)

## API 调用

将 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。素材地址为示例。

```json
{
  "model": "minimax/h3-fast/reference-to-video",
  "prompt": "保留图片中蓝色陶瓷杯的造型，沿桌面慢慢推进。",
  "refers": [{ "url": "https://example.com/cup.png", "type": "image" }],
  "duration": 8,
  "resolution": "480P",
  "ratio": "16:9",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 中读取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-fast/reference-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

默认区包含提示词、每种素材的第一个槽位、时长和画面比例。其余素材和扩写位于高级区，固定 480P 分辨率位于隐藏区。维护账号可以通过「编辑参数」调整布局和说明。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
