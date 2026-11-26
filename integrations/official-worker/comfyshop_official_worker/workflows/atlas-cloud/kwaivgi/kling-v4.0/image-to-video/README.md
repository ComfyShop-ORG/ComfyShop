# 可灵 4.0 图生视频

以起始图生成 3 至 30 秒的视频，可加入中间关键帧和结束图。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/image-to-video)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                               | 必填 | 默认值                              | 输入约定                                                            |
| --------------- | ------------------------------------------------------------ | ---- | ----------------------------------- | ------------------------------------------------------------------- |
| `model`         | `execution.config.model`                                     | 是   | `kwaivgi/kling-v4.0/image-to-video` | 工作机从执行配置读取                                                |
| `prompt`        | `prompt`                                                     | 否   | 官方示例                            | 动作、运镜或希望避免的内容。英文最多 26,000 字符，非英文最多 11,000 |
| `image`         | `first_frame` 或 `first_frame_source`                        | 是   | 无                                  | JPEG / PNG，最多 30 MB，每边至少 300 像素，宽高比为 2:5 至 5:2      |
| `middle_images` | `middle_frame_1` 至 `middle_frame_8`、`middle_frame_sources` | 否   | 省略                                | 按时间线排序，最多 8 张                                             |
| `last_image`    | `last_frame` 或 `last_frame_source`                          | 否   | 省略                                | 结束关键帧                                                          |
| `duration`      | `duration`                                                   | 否   | 10                                  | 3 至 30 秒的整数                                                    |
| `resolution`    | `resolution`                                                 | 否   | `1080p`                             | `720p`、`1080p`、`4k`、`1080p-esr`、`2k-esr`、`4k-esr`              |
| `dynamic_range` | `dynamic_range`                                              | 否   | `sdr`                               | `sdr` 或 `hdr`。10 位 HDR 只用于原生 `1080p` 或 `4k`                |

关键帧可以上传，也可填写单个公开图片 URL 或 Base64。起始、中间、结束关键帧合计最多 10 张，按此顺序在提示词中引用 `@image_N`。多张中间帧先使用上传顺序，再追加逐行填写的来源。ComfyShop 将每个来源字段限制为 4 MiB。Atlas 检查按语言区分的提示词长度及外部素材属性。ESR 保留原始宽高比，Atlas 分别计收视频生成和增强费用。 [官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0/image-to-video",
  "image": "https://example.com/opening.jpg",
  "middle_images": ["https://example.com/middle.jpg"],
  "last_image": "https://example.com/closing.jpg",
  "prompt": "镜头从 @image_1 开始，经过 @image_2 的近景，最后停在 @image_3。",
  "duration": 10,
  "resolution": "1080p",
  "dynamic_range": "sdr"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始和结束关键帧、提示词、时长、分辨率与动态范围位于默认区。中间关键帧和全部来源字段位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
