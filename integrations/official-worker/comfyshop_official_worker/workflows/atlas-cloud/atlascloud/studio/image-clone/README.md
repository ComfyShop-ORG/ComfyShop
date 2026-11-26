# Atlas Cloud Studio 图像复刻

把自己的商品放入参考图的场景。可沿用原图构图与光线，也可参照风格重新创作。 Atlas Cloud 模型 ID 为 `atlascloud/studio/image-clone`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/image-clone)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                          | 必填 | 默认值                          | 输入约定                                                                 |
| ----------------- | --------------------------------------- | ---- | ------------------------------- | ------------------------------------------------------------------------ |
| `model`           | `execution.config.model`                | 是   | `atlascloud/studio/image-clone` | 工作机从执行配置读取                                                     |
| `product_image`   | `product_image` 或 `product_source`     | 是   | 无                              | 商品图，单个上传文件最多 10 MB，也可提供公开图片 URL                     |
| `reference_image` | `reference_image` 或 `reference_source` | 是   | 无                              | 参考图，单个上传文件最多 10 MB，也可提供公开图片 URL                     |
| `user_prompt`     | `user_prompt`                           | 是   | 无                              | 描述商品及要保留或调整的元素                                             |
| `visual_type`     | `visual_type`                           | 否   | `Reference Clone`               | `Reference Clone` 参考复刻，`Exact Clone` 保留构图、光线和背景并替换商品 |
| `ratio`           | `ratio`                                 | 否   | `3:4`                           | `1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`16:9`、`9:16`、`21:9`                |
| `resolution`      | `resolution`                            | 否   | `2k`                            | `1k`、`2k` 或 `4k`                                                       |
| `format`          | `format`                                | 否   | `png`                           | `png` 或 `jpeg`                                                          |
| `count`           | `count`                                 | 否   | 1                               | `1`、`2`、`3` 或 `4`                                                     |

商品和参考图片分别提交。Atlas 将生成的图片按 `outputs` 顺序返回。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-image-clone.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-image-clone-v4.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-image-clone)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/image-clone#usage-examples)

```json
{
  "model": "atlascloud/studio/image-clone",
  "product_image": "https://example.com/product.png",
  "reference_image": "https://example.com/studio-reference.jpg",
  "user_prompt": "把原图中的玻璃杯换成上传的蓝色保温杯，沿用自然光和浅色桌面。",
  "visual_type": "Reference Clone",
  "ratio": "3:4",
  "resolution": "2k",
  "format": "png",
  "count": 2
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

两张图、创作指令、复刻模式和画面比例位于默认区。图片 URL、出图张数、分辨率与成品格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
