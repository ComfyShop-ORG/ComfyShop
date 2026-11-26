# 可灵 Image 4.0 文生图

从文字生成一张或多张独立图片，可使用参考图引导画面。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-image-v4.0/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/text-to-image)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                       | 必填 | 默认值                                   | 输入约定                                                                                              |
| ------------------ | ---------------------------------------------------- | ---- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                             | 是   | `kwaivgi/kling-image-v4.0/text-to-image` | 工作机从执行配置读取                                                                                  |
| `prompt`           | `prompt`                                             | 是   | 无                                       | 描述画面主体、构图和风格。用 `@image_1`、`@image_2` 等引用素材                                        |
| `reference_images` | `reference_1` 至 `reference_10`、`reference_sources` | 否   | 省略                                     | 最多 10 张 JPEG 或 PNG，每张最多 30 MB，每边至少 300 像素，宽高比为 2:5 至 5:2。支持上传、URL、Base64 |
| `num_images`       | `num_images`                                         | 否   | 1                                        | 1 至 9 的整数                                                                                         |
| `resolution`       | `resolution`                                         | 否   | `2k`                                     | `2k`、`4k` 或 `8k`                                                                                    |
| `aspect_ratio`     | `aspect_ratio`                                       | 否   | `auto`                                   | `auto`、`16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`3:2`、`2:3`、`21:9`                                     |

工作机按 `outputs` 顺序保存各张成品。上传参考图先于填写的 URL 和 Base64 发送，编号跳过空槽。Base64 文本遵循 ComfyShop 的单字段 4 MiB 上限。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-image-v4.0-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-image-v4.0-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-image-v4.0-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/text-to-image#usage-examples)

```json
{
  "model": "kwaivgi/kling-image-v4.0/text-to-image",
  "prompt": "为 @image_1 中的陶瓷茶壶制作一张产品图片，使用浅色背景和自然窗光。",
  "reference_images": ["https://example.com/teapot.png"],
  "num_images": 1,
  "resolution": "2k",
  "aspect_ratio": "3:4"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、出图张数、分辨率和比例位于默认区。其余参考图及图片来源位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
