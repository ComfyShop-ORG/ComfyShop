# 可灵 Image 4.0 组图

按提示词生成一组相互连贯的图片，可使用共同的参考图维持角色、商品和风格一致。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-image-v4.0/image-set`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/image-set)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                                       | 必填 | 默认值                               | 输入约定                                                                                              |
| ------------------ | ---------------------------------------------------- | ---- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `model`            | `execution.config.model`                             | 是   | `kwaivgi/kling-image-v4.0/image-set` | 工作机从执行配置读取                                                                                  |
| `prompt`           | `prompt`                                             | 是   | 无                                   | 描述图片组的内容、顺序和风格。用 `@image_1`、`@image_2` 等引用素材                                    |
| `reference_images` | `reference_1` 至 `reference_10`、`reference_sources` | 否   | 省略                                 | 最多 10 张 JPEG 或 PNG，每张最多 30 MB，每边至少 300 像素，宽高比为 2:5 至 5:2。支持上传、URL、Base64 |
| `num_images`       | `num_images`                                         | 否   | 4                                    | 2 至 10 的整数                                                                                        |
| `resolution`       | `resolution`                                         | 否   | `2k`                                 | `2k`、`4k` 或 `8k`                                                                                    |
| `aspect_ratio`     | `aspect_ratio`                                       | 否   | `auto`                               | `auto`、`16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`3:2`、`2:3`、`21:9`                                     |

工作机按 `outputs` 顺序保存整组图。上传参考图先于填写的 URL 和 Base64 发送，编号跳过空槽。Base64 文本遵循 ComfyShop 的单字段 4 MiB 上限。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-image-v4.0-image-set.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-image-v4.0-image-set.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-image-v4.0-image-set.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-image-v4.0/image-set#usage-examples)

```json
{
  "model": "kwaivgi/kling-image-v4.0/image-set",
  "prompt": "为 @image_1 中的陶瓷茶壶制作四张风格连贯的图片，依次展示正面、釉面细节、倒茶和茶桌场景。",
  "reference_images": ["https://example.com/teapot.png"],
  "num_images": 4,
  "resolution": "2k",
  "aspect_ratio": "3:4"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、出图张数、分辨率和比例位于默认区。其余参考图及图片来源位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
