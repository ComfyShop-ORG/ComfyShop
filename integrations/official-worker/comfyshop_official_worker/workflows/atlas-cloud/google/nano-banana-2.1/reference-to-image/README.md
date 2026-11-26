# Nano Banana 2.1 参考视频生图

从一段视频、提示词及可选参考图生成静态图片。 Atlas Cloud 模型 ID 为 `google/nano-banana-2.1/reference-to-image`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2.1/reference-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填       | 默认值                                      | 输入约定                                                               |
| ---------------------- | ---------------------------------------------------- | ---------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是         | `google/nano-banana-2.1/reference-to-image` | 工作机从执行配置读取                                                   |
| `prompt`               | `prompt`                                             | 是         | 无                                          | 描述画面、视频里的主体或关键时刻                                       |
| `video_clips[].url`    | `video` 或 `video_source`                            | 是         | 无                                          | 一段最长 25 分钟的视频。支持上传、公开 HTTP(S) 视频地址或 YouTube 地址 |
| `video_clips[].start`  | `video_start`                                        | 对象内必填 | 0                                           | 开始秒数，非负                                                         |
| `video_clips[].ends`   | `video_end`                                          | 对象内必填 | 0                                           | 结束秒数，0 表示到末尾。其他取值必须大于开始秒数                       |
| `video_clips[].fps`    | `video_fps`                                          | 对象内必填 | 1                                           | 数值 0 至 24，指定采样帧率                                             |
| `reference_images`     | `reference_1` 至 `reference_14`、`reference_sources` | 否         | 无                                          | 提供时为 1 至 14 张，每张最大 7 MB。支持 PNG、JPEG、WebP、HEIC 或 HEIF |
| `aspect_ratio`         | `aspect_ratio`                                       | 否         | `auto`                                      | Schema 的 15 个选项。自动模式由模型决定比例                            |
| `resolution`           | `resolution`                                         | 否         | `1k`                                        | `1k`、`2k` 或 `4k`                                                     |
| `thinking_level`       | `thinking_level`                                     | 否         | `default`                                   | `default`、`minimal`、`medium` 或 `high`。模型默认使用中等档           |
| `enable_web_search`    | `enable_web_search`                                  | 否         | false                                       | 使用 Google 网页搜索补充实时信息                                       |
| `enable_image_search`  | `enable_image_search`                                | 否         | false                                       | 使用 Google 图片搜索提供视觉参考，可独立开启                           |
| `media_resolution`     | `media_resolution`                                   | 否         | `default`                                   | `default`、`low`、`medium`、`high`，控制视频帧与参考图的处理细节       |
| `top_p`                | `top_p`                                              | 否         | 0.95                                        | 数值 0 至 1                                                            |
| `temperature`          | `temperature`                                        | 否         | 1                                           | 数值 0 至 1                                                            |
| `seed`                 | `seed`                                               | 否         | -1                                          | 整数。-1 使用随机种子                                                  |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否         | false                                       | 等待完成后从提交响应取结果                                             |
| `enable_base64_output` | `enable_base64_output`                               | 否         | false                                       | 返回 Base64 图片，由工作机解码保存                                     |

视频上传和地址只能选择一项。工作机把素材地址、起止秒数与采样帧率组装成 `video_clips` 数组中的一项。参考图按上传编号排序，再追加文本区的公开地址或 Base64，文本字段上限为 4 MiB。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2.1-reference-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2.1-reference-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2.1-reference-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2.1/reference-to-image#usage-examples)

```json
{
  "model": "google/nano-banana-2.1/reference-to-image",
  "prompt": "根据这段自行车赛视频做一张封面，保留弯道和主体骑手，加入清晰的标题。",
  "video_clips": [
    {
      "url": "https://example.com/race.mp4",
      "start": 12.5,
      "ends": 18,
      "fps": 1
    }
  ],
  "aspect_ratio": "16:9",
  "resolution": "2k"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、参考视频、比例和分辨率位于默认区。公开视频地址、视频剪辑、参考图及生成细节位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
