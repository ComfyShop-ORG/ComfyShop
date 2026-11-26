# Nano Banana 2 Developer 参考视频生图

根据一段视频和可选图片生成静态成品，支持剪辑时间和采样帧率。 Atlas Cloud 模型 ID 为 `google/nano-banana-2/reference-to-image-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2/reference-to-image-developer)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填       | 默认值                                              | 输入约定                                                         |
| ---------------------- | ---------------------------------------------------- | ---------- | --------------------------------------------------- | ---------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是         | `google/nano-banana-2/reference-to-image-developer` | 工作机从执行配置读取                                             |
| `prompt`               | `prompt`                                             | 是         | 无                                                  | 描述要生成的画面                                                 |
| `video_clips[].url`    | `video` 或 `video_source`                            | 是         | 无                                                  | 一段视频。上传或 HTTP(S) 直链视频最大 15 MB，也可用 YouTube 地址 |
| `video_clips[].start`  | `video_start`                                        | 对象内必填 | 0                                                   | 开始秒数，非负                                                   |
| `video_clips[].ends`   | `video_end`                                          | 对象内必填 | 0                                                   | 结束秒数。0 表示到视频末尾                                       |
| `video_clips[].fps`    | `video_fps`                                          | 对象内必填 | 1                                                   | 数值 0 至 24                                                     |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 否         | 无                                                  | 最多 10 张参考图，作为公开 HTTP(S) 地址发送                      |
| `aspect_ratio`         | `aspect_ratio`                                       | 否         | 由模型决定                                          | Schema 的 10 个比例预设                                          |
| `resolution`           | `resolution`                                         | 否         | `1k`                                                | `1k`、`2k` 或 `4k`                                               |
| `thinking_level`       | `thinking_level`                                     | 否         | `default`                                           | `default`、`high` 或 `minimal`                                   |
| `enable_web_search`    | `enable_web_search`                                  | 否         | false                                               | 使用 Google 网页搜索补充实时信息                                 |
| `top_p`                | `top_p`                                              | 否         | 0.95                                                | 数值 0 至 1                                                      |
| `temperature`          | `temperature`                                        | 否         | 1                                                   | 数值 0 至 1                                                      |
| `seed`                 | `seed`                                               | 否         | -1                                                  | 整数。-1 使用随机种子                                            |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否         | false                                               | 等待完成后从提交响应取结果                                       |
| `enable_base64_output` | `enable_base64_output`                               | 否         | false                                               | 返回 Base64 图片，由工作机解码保存                               |

选择上传视频或填写公开视频地址。工作机把素材地址和三个剪辑参数组装成 `video_clips` 数组中的一项。参考图先按编号发送，再按行追加公开地址。比例选择模型默认时省略 `aspect_ratio`。响应中的 `outputs` 用于保存成品图片。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-reference-to-image-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-reference-to-image-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-reference-to-image-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2/reference-to-image-developer#usage-examples)

```json
{
  "model": "google/nano-banana-2/reference-to-image-developer",
  "prompt": "为手工装订演示生成教程封面，突出缝线、纸张和书脊。",
  "video_clips": [
    {
      "url": "https://example.com/bookbinding.mp4",
      "start": 3.5,
      "ends": 10,
      "fps": 2
    }
  ],
  "images": ["https://example.com/book-cover.jpg"],
  "aspect_ratio": "16:9",
  "resolution": "2k"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、参考视频、比例和分辨率位于默认区。参考图片、地址、视频剪辑与生成细节位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
