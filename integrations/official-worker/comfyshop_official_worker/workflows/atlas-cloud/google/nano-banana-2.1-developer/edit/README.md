# Nano Banana 2.1 Developer 图像编辑

按提示词编辑或融合参考图，可通过给参考图画圈定位修改。 Atlas Cloud 模型 ID 为 `google/nano-banana-2.1-developer/edit`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2.1-developer/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                                  | 输入约定                                                      |
| ---------------------- | ---------------------------------------------------- | ---- | --------------------------------------- | ------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `google/nano-banana-2.1-developer/edit` | 工作机从执行配置读取                                          |
| `prompt`               | `prompt`                                             | 是   | 无                                      | 说明编辑目标，按提交顺序引用参考图，可在参考图上画圈定位      |
| `reference_images`     | `reference_1` 至 `reference_14`、`reference_sources` | 是   | 无                                      | 1 至 14 张，每张最大 7 MB。支持 PNG、JPEG、WebP、HEIC 或 HEIF |
| `aspect_ratio`         | `aspect_ratio`                                       | 否   | `auto`                                  | Schema 的 15 个选项。自动模式跟随输入图的比例                 |
| `resolution`           | `resolution`                                         | 否   | `1k`                                    | `1k`、`2k` 或 `4k`                                            |
| `thinking_level`       | `thinking_level`                                     | 否   | `default`                               | `default`、`minimal`、`medium` 或 `high`。模型默认使用中等档  |
| `enable_web_search`    | `enable_web_search`                                  | 否   | false                                   | 使用 Google 网页搜索补充实时信息                              |
| `enable_image_search`  | `enable_image_search`                                | 否   | false                                   | 使用 Google 图片搜索提供视觉参考，可独立开启                  |
| `media_resolution`     | `media_resolution`                                   | 否   | `default`                               | `default`、`low`、`medium`、`high`，控制参考图处理细节        |
| `top_p`                | `top_p`                                              | 否   | 0.95                                    | 数值 0 至 1                                                   |
| `temperature`          | `temperature`                                        | 否   | 1                                       | 数值 0 至 1                                                   |
| `seed`                 | `seed`                                               | 否   | -1                                      | 整数。-1 使用随机种子                                         |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                                   | 等待完成后从提交响应取结果                                    |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                   | 返回 Base64 图片，由工作机解码保存                            |

工作机先按编号发送上传文件，再按行追加公开 HTTP(S) 地址或 Base64 data URL。文本字段上限为 4 MiB，HEIC、HEIF 可通过该方式提供。圈线随图提交，提示词说明要修改的区域。以下示例地址需换成实际素材。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2.1-developer-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2.1-developer-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2.1-developer-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2.1-developer/edit#usage-examples)

```json
{
  "model": "google/nano-banana-2.1-developer/edit",
  "prompt": "保留原图的花束和花瓶，将桌布换成第二张图的细格纹样。",
  "reference_images": ["https://example.com/bouquet.jpg", "https://example.com/check-pattern.png"],
  "aspect_ratio": "4:5",
  "resolution": "2k",
  "media_resolution": "high"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、比例与分辨率位于默认区。其余参考图、素材地址、搜索、思考、参考图处理分辨率、采样和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
