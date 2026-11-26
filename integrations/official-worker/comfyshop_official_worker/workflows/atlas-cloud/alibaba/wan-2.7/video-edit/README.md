# Wan 2.7 视频编辑

按提示词编辑原视频，可用参考图引导画面，保留或调整时长与比例。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/video-edit`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/video-edit)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                                                        | 必填 | 默认值                       | 输入约定                                                         |
| ----------------- | --------------------------------------------------------------------- | ---- | ---------------------------- | ---------------------------------------------------------------- |
| `model`           | `execution.config.model`                                              | 是   | `alibaba/wan-2.7/video-edit` | 工作机从执行配置读取                                             |
| `video`           | `video` 或 `video_source`                                             | 是   | 无                           | MP4 或 MOV，2 至 10 秒，最多 100 MB。上传或给出公开 URL          |
| `prompt`          | `prompt`                                                              | 否   | 无                           | 描述编辑内容，最多 5,000 字符                                    |
| `negative_prompt` | `negative_prompt`                                                     | 否   | 无                           | 最多 500 字符                                                    |
| `images`          | `reference_image_1` 至 `reference_image_3`、`reference_image_sources` | 否   | 无                           | 至多三个公开图片 URL，单张最多 20 MB                             |
| `resolution`      | `resolution`                                                          | 否   | `1080P`                      | 原生 `720P` 或 `1080P`                                           |
| `ratio`           | `ratio`                                                               | 否   | 沿用原视频                   | `16:9`、`9:16`、`1:1`、`4:3` 或 `3:4`。选择沿用原视频时省略      |
| `duration`        | `duration`                                                            | 否   | 沿用原视频                   | 0 或省略时沿用原片时长。2 至 10 秒时从原片开头截取，工作流预设 0 |
| `prompt_extend`   | `prompt_extend`                                                       | 否   | true                         | 由模型扩写提示词                                                 |
| `seed`            | `seed`                                                                | 否   | -1                           | 整数范围 -1 至 2147483647。-1 使用随机种子                       |

参考图接受 JPEG、无透明通道的 PNG、BMP 或 WebP，宽高各 240 至 8000 像素，长短边比例最多 8:1。工作机将上传原件转换为素材地址。时长采用当前请求参数说明，静态模型介绍给出了 5 秒默认值。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-video-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-video-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-video-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-video-edit/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/video-edit#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/video-edit",
  "video": "https://example.com/cafe.mov",
  "prompt": "让咖啡厅中的灯光偏暖，保留原视频的运镜。",
  "images": ["https://example.com/warm-light.jpg"],
  "resolution": "1080P",
  "duration": 0,
  "prompt_extend": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、提示词、首张参考图、分辨率、比例和时长位于默认区。额外图片、素材地址、负面提示词、扩写与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
