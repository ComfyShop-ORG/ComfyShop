# HiDream O1 1.5 图片编辑

根据提示词编辑至少一张参考图，也可用多张图保持主体一致。 Atlas Cloud 模型 ID 为 `hidream-o1-1.5/edit`。[官方模型 API](https://www.atlascloud.ai/models/hidream-o1-1.5/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                              | 必填 | 默认值                | 输入约定                                                                                  |
| ---------------------- | ----------------------------------------------------------- | ---- | --------------------- | ----------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                                    | 是   | `hidream-o1-1.5/edit` | 工作机从执行配置读取                                                                      |
| `prompt`               | `prompt`                                                    | 是   | —                     | 最多 2,500 字符                                                                           |
| `reference_image_urls` | `reference_image_1` 至 `reference_image_4`、`image_sources` | 是   | —                     | 至少一张。接受上传和公开 HTTP(S) 地址，多张用于保持主体一致。                             |
| `image_size`           | `size_preset`                                               | 否   | `landscape_4_3`       | `square_hd`、`square`、`portrait_4_3`、`portrait_16_9`、`landscape_4_3`、`landscape_16_9` |
| `num_inference_steps`  | `num_inference_steps`                                       | 否   | `50`                  | 1 至 50 的整数                                                                            |
| `guidance_scale`       | `guidance_scale`                                            | 否   | `5`                   | 1 至 20 的数值                                                                            |
| `output_format`        | `output_format`                                             | 否   | `png`                 | `png`、`jpeg`、`webp`                                                                     |

提示词长度按请求 Schema 的 2,500 字符校验。接口说明提到自定义尺寸，公开请求只给出六个字符串枚举。示例数据中的 `num_images`、`keep_original_aspect` 和 `enable_safety_checker` 以及模型说明中的 `seed` 未列入该端点的请求参数。

[官方 Schema](https://static.atlascloud.ai/model/schema/hidream-o1-1.5-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/hidream-o1-1.5-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/hidream-o1-1.5-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/hidream-o1-1.5/edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/hidream-o1-1.5/edit#usage-examples)

```json
{
  "model": "hidream-o1-1.5/edit",
  "prompt": "把海报上的文字移除，保留图像和配色。",
  "reference_image_urls": [
    "https://static.atlascloud.ai/media/images/dc5b5caecc5c5cd5d091ea92185c4956.jpg"
  ],
  "image_size": "square_hd",
  "num_inference_steps": 50,
  "guidance_scale": 5,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括第一张参考图、提示词、尺寸预设和输出格式。高级参数包括其余参考图、外部来源、推理步数与引导强度。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
