# Nano Banana 2 Lite 参考视频生图

从一段视频和可选参考图生成 1K 静态图片。 Atlas Cloud 模型 ID 为 `google/nano-banana-2-lite/reference-to-image`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2-lite/reference-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填       | 默认值                                         | 输入约定                                                                       |
| ---------------------- | ---------------------------------------------------- | ---------- | ---------------------------------------------- | ------------------------------------------------------------------------------ |
| `model`                | `execution.config.model`                             | 是         | `google/nano-banana-2-lite/reference-to-image` | 工作机从执行配置读取                                                           |
| `prompt`               | `prompt`                                             | 是         | 无                                             | 描述目标画面                                                                   |
| `video_clips[].url`    | `video` 或 `video_source`                            | 是         | 无                                             | 上传视频或使用公开视频地址。上传或 HTTP(S) 直链上限 15 MB，也可用 YouTube 地址 |
| `video_clips[].start`  | `video_start`                                        | 对象内必填 | 0                                              | 开始秒数，非负                                                                 |
| `video_clips[].ends`   | `video_end`                                          | 对象内必填 | 0                                              | 结束秒数，0 表示到末尾                                                         |
| `video_clips[].fps`    | `video_fps`                                          | 对象内必填 | 1                                              | 数值 0 至 24                                                                   |
| `images`               | `reference_1` 至 `reference_14`、`reference_sources` | 否         | 无                                             | 最多 14 张参考图，使用 HTTP(S) 图片地址                                        |
| `aspect_ratio`         | `aspect_ratio`                                       | 否         | `auto`                                         | Schema 的 15 个选项。自动模式由模型选择比例                                    |
| `resolution`           | `resolution`                                         | 否         | `1k`                                           | 仅 `1k`，工作流使用隐藏参数                                                    |
| `thinking_level`       | `thinking_level`                                     | 否         | `default`                                      | `default`、`high` 或 `minimal`                                                 |
| `top_p`                | `top_p`                                              | 否         | 0.95                                           | 数值 0 至 1                                                                    |
| `temperature`          | `temperature`                                        | 否         | 1                                              | 数值 0 至 1                                                                    |
| `seed`                 | `seed`                                               | 否         | -1                                             | 整数。-1 使用随机种子                                                          |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否         | false                                          | 等待完成后从提交响应取结果                                                     |
| `enable_base64_output` | `enable_base64_output`                               | 否         | false                                          | 返回 Base64 图片，由工作机解码保存                                             |

选择视频上传或公开 URL。工作机把视频地址和三个剪辑参数写入 `video_clips` 数组。可选图片先按编号发送上传图，再追加文本区的公开地址。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-lite-reference-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-lite-reference-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-lite-reference-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2-lite/reference-to-image#usage-examples)

```json
{
  "model": "google/nano-banana-2-lite/reference-to-image",
  "prompt": "根据视频中的焙茶过程生成一张教程封面，画面聚焦茶叶和手部动作。",
  "video_clips": [
    {
      "url": "https://example.com/roasted-tea.mp4",
      "start": 5,
      "ends": 9,
      "fps": 1
    }
  ],
  "aspect_ratio": "16:9",
  "resolution": "1k"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、参考视频与比例位于默认区。视频地址、剪辑、参考图和生成细节位于高级区。分辨率预设为 1K。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
