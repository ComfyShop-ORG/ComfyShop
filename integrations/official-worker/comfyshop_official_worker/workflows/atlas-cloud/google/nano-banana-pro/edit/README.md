# Nano Banana Pro 图像编辑

用提示词修改或融合一至十张参考图，可调整分辨率和成品格式。 Atlas Cloud 模型 ID 为 `google/nano-banana-pro/edit`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-pro/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                        | 输入约定                                                                       |
| ---------------------- | ---------------------------------------------------- | ---- | ----------------------------- | ------------------------------------------------------------------------------ |
| `model`                | `execution.config.model`                             | 是   | `google/nano-banana-pro/edit` | 工作机从执行配置读取                                                           |
| `prompt`               | `prompt`                                             | 是   | 无                            | 说明要保留或修改的图中元素                                                     |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                            | 一至十个图片 URL。工作机上传本地图片并获取 URL，之后追加逐行填写的公开图片 URL |
| `aspect_ratio`         | `aspect_ratio`                                       | 否   | 由模型决定                    | Schema 的 10 个比例预设                                                        |
| `resolution`           | `resolution`                                         | 否   | `1k`                          | `1k`、`2k` 或 `4k`                                                             |
| `enable_web_search`    | `enable_web_search`                                  | 否   | false                         | 使用 Google 网页搜索补充实时信息                                               |
| `media_resolution`     | `media_resolution`                                   | 否   | `default`                     | `default`、`low`、`medium` 或 `high`，控制素材处理细节                         |
| `output_format`        | `output_format`                                      | 否   | `default`                     | `default`、`png` 或 `jpeg`                                                     |
| `top_p`                | `top_p`                                              | 否   | 0.95                          | 数值 0 至 1                                                                    |
| `temperature`          | `temperature`                                        | 否   | 1                             | 数值 0 至 1                                                                    |
| `seed`                 | `seed`                                               | 否   | -1                            | 整数。-1 使用随机种子                                                          |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                         | 等待完成后从提交响应取结果                                                     |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                         | 返回 Base64 图片，由工作机解码保存                                             |

比例选择模型默认时，工作机省略 `aspect_ratio`。工作机按 `outputs` 保存生成结果。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-pro-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-pro-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-pro-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-pro/edit#usage-examples)

```json
{
  "model": "google/nano-banana-pro/edit",
  "prompt": "保留兰花结构和颜色，把背景替换为柔光摄影棚。",
  "images": ["https://example.com/orchid.jpg"],
  "aspect_ratio": "3:4",
  "resolution": "4k",
  "output_format": "png",
  "enable_web_search": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、比例、分辨率和格式位于默认区。其余参考图、图片网址、网页搜索、素材处理、采样、种子及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
