# Seedream v5.5 图层拆分

将一张原图分解成一张底图与最多 99 张透明 PNG 图层，并可识别常规印刷文字。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.5/layer-decomposition`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/layer-decomposition)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段            | 必填 | 默认值                                        | 输入约定                                                                   |
| ------------------------- | ------------------------- | ---- | --------------------------------------------- | -------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`  | 是   | `bytedance/seedream-v5.5/layer-decomposition` | 工作机从执行配置读取                                                       |
| `image`                   | `image` 或 `image_source` | 是   | 无                                            | 单张 PNG 或 JPEG 的公开 URL 或 Base64 data URL                             |
| `prompt`                  | `prompt`                  | 否   | 自动拆分                                      | 自然语言说明或 `<bbox>x1 y1 x2 y2</bbox>`，坐标从左上角按 0 至 1000 归一化 |
| `resolution`              | `resolution`              | 否   | `auto`                                        | `auto`、`1k`、`1.5k`、`2k`，保留每张成品各自的宽高比                       |
| `num_images`              | `num_images`              | 否   | 30                                            | 整数 2 至 100，限制底图与图层的总张数                                      |
| `enable_text_recognition` | `enable_text_recognition` | 否   | false                                         | 识别常规印刷文字的正文、行坐标及文字样式                                   |
| `output_format`           | `output_format`           | 否   | `png`                                         | 底图为 `png` 或 `jpeg`，图层均为透明 PNG                                   |
| `enable_sync_mode`        | `enable_sync_mode`        | 否   | false                                         | 完成后从提交响应直接取结果                                                 |
| `enable_base64_output`    | `enable_base64_output`    | 否   | false                                         | 返回 Base64 图片，由工作机解码保存                                         |

总像素为 262144 至 36000000，宽高比为 1:16 至 16:1，原图最大 30 MB。上传和地址二选一，文本字段上限为 4 MiB。分解结果底图在首位，后续为按 `z_index` 升序返回的透明图层。工作机将按索引对应的 `image_results` 与 `layers` 保存到同一 JSON 文件。图层记录坐标、名称与说明。启用识别后，在可识别的文字层中保存 `text_recognition`，包括正文、每行坐标和字形、颜色等样式。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.5-layer-decomposition.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.5-layer-decomposition.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.5-layer-decomposition.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例 URL 换成实际的 PNG 或 JPEG 原图。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/layer-decomposition#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.5/layer-decomposition",
  "image": "https://example.com/weekend-market.jpg",
  "prompt": "将周末市集海报的标题、日期、配图和背景拆成独立图层。",
  "resolution": "1.5k",
  "num_images": 10,
  "enable_text_recognition": true,
  "output_format": "png",
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图、拆分说明、分辨率和最多输出张数位于默认区。素材地址、识别开关、底图格式及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
