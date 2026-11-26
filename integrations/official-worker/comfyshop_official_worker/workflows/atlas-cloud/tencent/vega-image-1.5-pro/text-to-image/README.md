# 腾讯 Vega 1.5 Pro 文生图

根据文字生成 1K、2K 或 4K 图像，可配置反向提示词和提示词增强。 Atlas Cloud 模型 ID 为 `tencent/vega-image-1.5-pro/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-image-1.5-pro/text-to-image)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段           | 必填 | 默认值                                     | 输入约定                                             |
| ----------------- | ------------------------ | ---- | ------------------------------------------ | ---------------------------------------------------- |
| `model`           | `execution.config.model` | 是   | `tencent/vega-image-1.5-pro/text-to-image` | 工作机从执行配置读取                                 |
| `prompt`          | `prompt`                 | 是   | 官方示例                                   | 描述生成主体、场景和风格                             |
| `size`            | `size`                   | 否   | `1K`                                       | `1K`、`2K`、`4K`，Atlas 也接受 `resolution` 作为别名 |
| `aspect_ratio`    | `aspect_ratio`           | 否   | `1:1`                                      | `16:9`、`9:16`、`1:1`、`3:4`、`4:3`                  |
| `negative_prompt` | `negative_prompt`        | 否   | 省略                                       | 描述画面中希望避开的内容                             |
| `enhance_prompt`  | `enhance_prompt`         | 否   | `false`                                    | 是否增强提示词                                       |
| `seed`            | `seed`                   | 否   | 省略                                       | 用整数指定随机种子                                   |
| `input_region`    | `input_region`           | 否   | `Oversea`                                  | `Mainland`、`Oversea`、`OverseaUSWest`，用于内容审核 |

工作机使用 `size` 提交尺寸档位，留空的反向提示词和种子会省略。每次生成一张图。 [官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-image-1.5-pro-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-image-1.5-pro-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-image-1.5-pro-text-to-image.md) · [Vega Image 1.5 系列](https://www.atlascloud.ai/models/wand-vega-image-1.5)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-image-1.5-pro/text-to-image#usage-examples)

```json
{
  "model": "tencent/vega-image-1.5-pro/text-to-image",
  "prompt": "一座弧形石桥跨过平静的湖面，远处的山影倒映在水中。",
  "size": "1K",
  "aspect_ratio": "1:1",
  "negative_prompt": "画面中的文字、水印",
  "enhance_prompt": false,
  "input_region": "Oversea"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、分辨率、画面比例位于默认区。反向提示词、提示词增强、种子和输入地区位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
