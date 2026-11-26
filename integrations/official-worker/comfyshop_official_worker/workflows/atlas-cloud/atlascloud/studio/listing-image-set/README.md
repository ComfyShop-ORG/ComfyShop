# Atlas Cloud Studio 商品详情图套组

通过商品图或商品页面生成多种商品图。每种所选类型生成一张。 Atlas Cloud 模型 ID 为 `atlascloud/studio/listing-image-set`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/listing-image-set)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                                                                     | 必填               | 默认值                                | 输入约定                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------- | ------------------ | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`                                                                           | 是                 | `atlascloud/studio/listing-image-set` | 工作机从执行配置读取                                                                                                  |
| `link`          | `link`                                                                                             | 与商品图至少一项   | 省略                                  | 公开商品页 URL，Atlas 会从页面提取规格、卖点与主图                                                                    |
| `product_image` | `product_image` 或 `product_source`                                                                | 与商品链接至少一项 | 省略                                  | 商品图片，单个上传文件最多 10 MB，也可使用公开图片 URL                                                                |
| `model_image`   | `model_image` 或 `model_source`                                                                    | 否                 | 省略                                  | 可选模特图，单个上传文件最多 10 MB，也可使用公开图片 URL                                                              |
| `user_prompt`   | `user_prompt`                                                                                      | 否                 | 省略                                  | 描述品牌、卖点、受众和希望的风格                                                                                      |
| `visual_type`   | `main_image`、`multi_angle`、`detail_shot`、`feature_image`、`size_specs`、`on_model`、`lifestyle` | 是                 | `Main Image`                          | `Main Image`、`Multi-angle View`、`Detail Shot`、`Feature Image`、`Size & Specs`、`On-model Image`、`Lifestyle Image` |
| `ratio`         | `ratio`                                                                                            | 否                 | `3:4`                                 | `1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`16:9` 或 `9:16`                                                                   |
| `resolution`    | `resolution`                                                                                       | 否                 | `2k`                                  | `1k`、`2k` 或 `4k`                                                                                                    |
| `format`        | `format`                                                                                           | 否                 | `png`                                 | `png` 或 `jpeg`                                                                                                       |

工作机按官方调用说明要求至少提供商品链接或商品图。勾选的类型按界面顺序拼成以英文逗号分隔的字符串，每种类型生成一张。当前 Schema 的 `visual_type` 定义给出了出图数量规则，`count` 只出现在字段顺序中。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-listing-image-set.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-listing-image-set-v6.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-listing-image-set)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/listing-image-set#usage-examples)

```json
{
  "model": "atlascloud/studio/listing-image-set",
  "product_image": "https://example.com/product.png",
  "visual_type": "Main Image, Detail Shot, Lifestyle Image",
  "user_prompt": "保持杯身的浅蓝色，突出细腻哑光纹理。",
  "ratio": "3:4",
  "resolution": "2k",
  "format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

商品链接、图片、创作指令、图像类型和比例位于默认区。素材 URL、分辨率和成品格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
