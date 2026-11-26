# 可灵 Image 4.0 长图

将页面主视觉、商品展示和内容区生成一张完整长图，支持电商详情页与网页视觉设计。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-image-v4.0/long-image`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/long-image)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                      | 必填     | 默认值                                | 输入约定                                                                                                  |
| ------------------ | --------------------------------------------------- | -------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                            | 是       | `kwaivgi/kling-image-v4.0/long-image` | 工作机从执行配置读取                                                                                      |
| `prompt`           | `prompt`                                            | 是       | 无                                    | 描述页面内容、结构和风格。可用 `@image_1`、`@image_2` 等引用参考图                                        |
| `skill`            | `skill`                                             | 是       | 表单预选 `ecommerce`                  | `ecommerce` 电商详情页，`webpage` 网页视觉设计                                                            |
| `reference_images` | `reference_1` 至 `reference_3`、`reference_sources` | 电商必填 | 省略                                  | 电商需要 1 至 3 张，网页允许 0 至 3 张。JPEG 或 PNG，每张最多 30 MB，每边至少 300 像素，宽高比 2:5 至 5:2 |
| `length`           | `length`                                            | 否       | `medium`                              | 电商模式可选 `short`（约 2 至 5 区块）、`medium`（约 6 至 10）、`long`（约 11 至 18）                     |
| `resolution`       | `resolution`                                        | 否       | `1k`                                  | `1k` 或 `2k`                                                                                              |

每次生成一张长图。参考图可上传，也可填写公开 URL 或 Base64。ComfyShop 对单个素材来源文本框限制为 4 MiB。更大的图片可上传或使用公开 URL。网页模式下工作机省略 `length`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-image-v4.0-long-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-image-v4.0-long-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-image-v4.0-long-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/long-image#usage-examples)

```json
{
  "model": "kwaivgi/kling-image-v4.0/long-image",
  "prompt": "为 @image_1 中的陶瓷茶壶设计详情长图，包含主图、釉面细节、容量和保养说明。",
  "skill": "ecommerce",
  "reference_images": ["https://example.com/teapot.png"],
  "length": "medium",
  "resolution": "2k"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

页面类型、提示词、第一张参考图、内容长度与分辨率位于默认区。更多参考图和图片来源位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
