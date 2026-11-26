# Seedream v5.5 图像编辑

按提示词与参考图编辑图片，支持原生透明 PNG。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.5/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                         | 输入约定                                                                                    |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------------ | ------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v5.5/edit` | 工作机从执行配置读取                                                                        |
| `prompt`               | `prompt`                                             | 是   | 无                             | 描述改动，可用坐标或原图上的框、箭头定位。建议不超过 300 个中文字符或 600 个英文单词        |
| `reference_images`     | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                             | 1 至 10 个公开 URL 或 Base64 data URL，支持 JPEG、PNG、WebP、BMP、TIFF、GIF、HEIC、HEIF     |
| `size`                 | `size`                                               | 否   | `2048*2048`                    | 24 个 1K、1.5K、2K 预设。需要保留参考图宽高比时，选择相匹配的预设                           |
| `output_format`        | `output_format`                                      | 否   | `png`                          | `png` 或 `jpeg`                                                                             |
| `background`           | `background`                                         | 否   | `auto`                         | `auto`、`transparent` 或 `opaque`。透明输出要求 PNG，可接受 1 至 10 张带或不带 Alpha 的源图 |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                          | 等待生成完成后在提交响应中取结果                                                            |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                          | 返回 Base64 图片，由工作机解码保存                                                          |

每张来源最大 30 MB。宽、高均须大于 14 像素，总像素上限 36000000，宽高比限 1:16 至 16:1。工作机检查上传原图，并按槽位顺序发送，再追加文本区的 URL 或 Base64。文本字段上限为 4 MiB。Atlas 会校验地址和内联素材的尺寸。结果实际背景保存在 `image_results` JSON 成品中。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.5-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.5-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.5-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址换成实际素材。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/edit#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.5/edit",
  "prompt": "保留第一张图中的玻璃壶，参考第二张的釉色重新着色，移除背景。",
  "reference_images": ["https://example.com/pitcher.jpg", "https://example.com/glaze.jpg"],
  "size": "1536*1536",
  "output_format": "png",
  "background": "transparent"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图和尺寸位于默认区。其余参考图、素材地址、格式、背景和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
