# Wan 2.7 图像编辑

按提示词修改主图，可用其他图片参考构图、材质或风格。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/image-edit`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/image-edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                      | 必填 | 默认值                       | 输入约定                                                      |
| ---------------------- | --------------------------------------------------- | ---- | ---------------------------- | ------------------------------------------------------------- |
| `model`                | `execution.config.model`                            | 是   | `alibaba/wan-2.7/image-edit` | 工作机从执行配置读取                                          |
| `prompt`               | `prompt`                                            | 是   | 无                           | 说明要修改的内容与参考图的用途，最多 5,000 字符               |
| `images`               | `reference_1` 至 `reference_9`、`reference_sources` | 是   | 无                           | 一至九张。接受上传、公开 URL 或 Base64 数据网址。第一张是主图 |
| `size`                 | `size`                                              | 否   | `2K`                         | `1K` 或 `2K`                                                  |
| `n`                    | `n`                                                 | 否   | 1                            | 1 至 4 张                                                     |
| `watermark`            | `watermark`                                         | 否   | false                        | 可在成品右下角添加 AI 生成标识                                |
| `thinking_mode`        | `thinking_mode`                                     | 否   | true                         | 启用思考模式                                                  |
| `seed`                 | `seed`                                              | 否   | -1                           | 整数范围 -1 至 2147483647。-1 使用随机种子                    |
| `enable_sync_mode`     | `enable_sync_mode`                                  | 否   | false                        | 等待生成完成                                                  |
| `enable_base64_output` | `enable_base64_output`                              | 否   | false                        | 返回 Base64 图片                                              |

上传图排在手工填写的地址之前。输入接受 JPEG、无透明通道的 PNG、BMP 或 WebP。宽高各 240 至 8000 像素，长短边比例最多 8:1，单张最多 20 MB。文本来源框最多容纳 4,194,304 个字符。Atlas 的模型说明列出水印控制，厂商 API 给出布尔值和默认设置。尺寸采用 Atlas 端点的预设。[阿里云模型参数](https://www.alibabacloud.com/help/en/model-studio/wan-image-generation-and-editing-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-image-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-image-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-image-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-image-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/image-edit#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/image-edit",
  "prompt": "保留主图的陶瓷杯和构图，把桌面改成第二张图中的深色木材。",
  "images": ["https://example.com/cup.jpg", "https://example.com/wood.webp"],
  "size": "2K",
  "n": 2,
  "watermark": false,
  "thinking_mode": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张图、尺寸和张数位于默认区。其他参考图、素材来源、水印、思考模式、种子及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
