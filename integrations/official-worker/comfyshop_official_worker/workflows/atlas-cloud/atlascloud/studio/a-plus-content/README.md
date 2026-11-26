# Atlas Cloud Studio A+ 商品展示图

用商品页或商品图生成 A+ 内容模块图片，每种所选模块生成一张。 Atlas Cloud 模型 ID 为 `atlascloud/studio/a-plus-content`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/a-plus-content)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                                            | 必填               | 默认值                             | 输入约定                                                                                                                                           |
| --------------- | ------------------------------------------------------------------------- | ------------------ | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`                                                  | 是                 | `atlascloud/studio/a-plus-content` | 工作机从执行配置读取                                                                                                                               |
| `link`          | `link`                                                                    | 与商品图至少一项   | 省略                               | 公开商品页 URL，Atlas 会提取规格、卖点与主图                                                                                                       |
| `product_image` | `product_image` 或 `product_source`                                       | 与商品链接至少一项 | 省略                               | 上传商品图，最多 10 MB，也可使用公开图片 URL                                                                                                       |
| `model_image`   | `model_image` 或 `model_source`                                           | 否                 | 省略                               | 上传模特图，最多 10 MB，也可使用公开图片 URL                                                                                                       |
| `user_prompt`   | `user_prompt`                                                             | 否                 | 省略                               | 描述品牌、卖点、受众和期望风格                                                                                                                     |
| `visual_type`   | `hero`、`feature`、`scene`、`detail`、`spec`、`comparison`、`brand_story` | 是                 | `hero`                             | 可多选。首屏主视觉 `hero`、卖点介绍 `feature`、场景展示 `scene`、细节特写 `detail`、参数说明 `spec`、产品对比 `comparison`、品牌故事 `brand_story` |
| `ratio`         | `ratio`                                                                   | 否                 | `3:4`                              | `1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`16:9` 或 `9:16`                                                                                                |
| `resolution`    | `resolution`                                                              | 否                 | `2k`                               | `1k`、`2k` 或 `4k`                                                                                                                                 |
| `format`        | `format`                                                                  | 否                 | `png`                              | `png` 或 `jpeg`                                                                                                                                    |

工作机按官方调用说明要求至少提供商品链接或商品图，并把模块拼成英文逗号分隔的字符串。`visual_type` 的参数描述提到模块文案，预测响应和示例只提供图像 URL，工作机按公开响应保存图片。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-a-plus-content.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-a-plus-content-v5.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-a-plus-content)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/a-plus-content#usage-examples)

```json
{
  "model": "atlascloud/studio/a-plus-content",
  "product_image": "https://example.com/keyboard.png",
  "visual_type": "hero, detail, spec",
  "user_prompt": "展示木质键盘整体和键帽纹理，在规格模块写明外壳长 35 厘米。",
  "ratio": "3:4",
  "resolution": "2k",
  "format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

商品链接、图片、创作指令、内容模块和比例位于默认区。素材 URL、分辨率和成品格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
