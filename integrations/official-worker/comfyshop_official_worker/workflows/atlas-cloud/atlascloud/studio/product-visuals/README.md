# Atlas Cloud Studio 商品视觉广告

用商品照片生成主图、详情页或宣传海报，可指定模特照片。 Atlas Cloud 模型 ID 为 `atlascloud/studio/product-visuals`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/product-visuals)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                      | 必填 | 默认值                              | 输入约定                                                                                      |
| --------------- | ----------------------------------- | ---- | ----------------------------------- | --------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`            | 是   | `atlascloud/studio/product-visuals` | 工作机从执行配置读取                                                                          |
| `product_image` | `product_image` 或 `product_source` | 是   | 无                                  | 商品图，上传最多 10 MB，也可提供公开图片 URL                                                  |
| `model_image`   | `model_image` 或 `model_source`     | 否   | 省略                                | 模特图，上传最多 10 MB，也可提供公开图片 URL                                                  |
| `user_prompt`   | `user_prompt`                       | 是   | 无                                  | 描述品牌、亮点和想要的风格                                                                    |
| `visual_type`   | `visual_type`                       | 否   | `product_hero`                      | 商品主图 `product_hero`、详情页 `product_detail`、宣传海报 `promo_poster`。选择自动判断时省略 |
| `ratio`         | `ratio`                             | 否   | `9:16`                              | `1:1`、`3:4`、`4:3`、`16:9`、`9:16`                                                           |
| `resolution`    | `resolution`                        | 否   | `2k`                                | `1k`、`2k` 或 `4k`。实际像素依比例而定，3:4 和 4:3 没有中间像素档，1:1 上限为 2048 像素       |
| `format`        | `format`                            | 否   | `png`                               | `png` 或 `jpeg`                                                                               |
| `count`         | `count`                             | 否   | 1                                   | `1`、`2`、`3` 或 `4`                                                                          |

分辨率档位按官方枚举发送。Atlas 会根据比例确定最终像素尺寸。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-product-visuals.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-product-visuals-v2.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-product-visuals)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/studio-product-visuals/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/product-visuals#usage-examples)

```json
{
  "model": "atlascloud/studio/product-visuals",
  "product_image": "https://example.com/desk-lamp.png",
  "user_prompt": "为哑光台灯制作宣传海报，使用米白背景和柔和侧光。",
  "visual_type": "promo_poster",
  "ratio": "9:16",
  "resolution": "2k",
  "format": "png",
  "count": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

商品图、模特图、创作指令、视觉类型与画面比例位于默认区。图片 URL、出图张数、分辨率与成品格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
