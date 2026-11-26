# Atlas Cloud Qwen Image 文生图

根据文字生成图片，适合制作海报、插画和带有文字的图像。 Atlas Cloud 模型 ID 为 `atlascloud/qwen-image/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/qwen-image/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                | 输入约定                                              |
| ---------------------- | ------------------------ | ---- | ------------------------------------- | ----------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `atlascloud/qwen-image/text-to-image` | 工作机从执行配置读取                                  |
| `prompt`               | `prompt`                 | 是   | 空字符串                              | 描述画面主体、风格和要呈现的文字，生成前须填写        |
| `size`                 | `size`                   | 否   | `1024*1024`                           | `宽*高`，每边 512 至 2048 像素，留空使用 Atlas 默认值 |
| `seed`                 | `seed`                   | 否   | -1                                    | 整数，-1 使用随机种子                                 |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | `false`                               | 开启后优先读取提交响应中的成品                        |
| `enable_base64_output` | `enable_base64_output`   | 否   | `false`                               | 开启后读取并保存 Base64 图片数据                      |

工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。静态示例和字段顺序提到了 `output_format`，当前端点参数表和 Schema 的请求属性未定义它的选项。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-qwen-image-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-qwen-image-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-qwen-image-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/qwen-image-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/qwen-image/text-to-image#usage-examples)

```json
{
  "model": "atlascloud/qwen-image/text-to-image",
  "prompt": "设计一本关于山间鸟类的书封面，标题为「山林鸟谱」，背景为淡绿色植物插画。",
  "size": "1024*1536",
  "seed": -1,
  "enable_sync_mode": false,
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词和图片尺寸位于默认区。种子、同步响应与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
