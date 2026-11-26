# Atlas Cloud Studio 服饰商品图

从服饰照片生成模特上身、空心人台、细节特写或平铺商品图。 Atlas Cloud 模型 ID 为 `atlascloud/studio/apparel-image`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/apparel-image)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                      | 必填 | 默认值                            | 输入约定                                                                                |
| --------------- | ----------------------------------- | ---- | --------------------------------- | --------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`            | 是   | `atlascloud/studio/apparel-image` | 工作机从执行配置读取                                                                    |
| `product_image` | `product_image` 或 `product_source` | 是   | 无                                | 服饰图，可平铺或挂拍。上传文件最多 10 MB，也可填写公开 URL                              |
| `model_image`   | `model_image` 或 `model_source`     | 否   | 无                                | 保留指定人物，上传文件最多 10 MB，也可填写公开 URL                                      |
| `visual_type`   | `visual_type`                       | 是   | `Model try-on`                    | `Model try-on` 模特上身，`Ghost Mannequin` 空心人台，`Detail` 细节特写，`Flat Lay` 平铺 |
| `user_prompt`   | `user_prompt`                       | 否   | 省略                              | 描述拍摄场景、姿势或重点                                                                |
| `ratio`         | `ratio`                             | 否   | `3:4`                             | `1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`16:9` 或 `9:16`                                     |
| `resolution`    | `resolution`                        | 否   | `2k`                              | `1k`、`2k` 或 `4k`                                                                      |
| `format`        | `format`                            | 否   | `png`                             | `png` 或 `jpeg`                                                                         |
| `count`         | `count`                             | 否   | 1                                 | `1`、`2`、`3` 或 `4`                                                                    |

空的拍摄指令和选填素材会省略。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-apparel-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-apparel-image-v4.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-apparel-image)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/apparel-image#usage-examples)

```json
{
  "model": "atlascloud/studio/apparel-image",
  "product_image": "https://example.com/linen-jacket.png",
  "user_prompt": "自然光下突出亚麻纹理和袖口细节。",
  "visual_type": "Detail",
  "ratio": "3:4",
  "resolution": "2k",
  "format": "png",
  "count": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

服饰图、模特图、创作指令、拍摄类型和画面比例位于默认区。图片 URL、出图张数、分辨率与成品格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
