# Midjourney V8.1 去除背景

去除图片背景，输出保留主体的透明 PNG。 Atlas Cloud 模型 ID 为 `midjourney/v8.1/remove-background`。[官方模型 API](https://www.atlascloud.ai/models/midjourney/v8.1/remove-background)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                        | 必填 | 默认值                              | 输入约定                          |
| ---------------------- | ------------------------------------- | ---- | ----------------------------------- | --------------------------------- |
| `model`                | `execution.config.model`              | 是   | `midjourney/v8.1/remove-background` | 工作机从执行配置读取              |
| `image`                | `input_image` 或 `input_image_source` | 是   | —                                   | 上传原图或提供公开 HTTPS 图片地址 |
| `enable_base64_output` | `enable_base64_output`                | 否   | `false`                             | Base64 图片由工作机解码后保存     |

Atlas 返回一张带透明通道的 PNG。

[官方 Schema](https://static.atlascloud.ai/model/schema/midjourney-v8.1-remove-background.json) · [官方示例数据](https://static.atlascloud.ai/model/example/midjourney-v8.1-remove-background.json) · [模型说明](https://static.atlascloud.ai/model/readme/midjourney-v8.1-remove-background.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/midjourney/v8.1/remove-background#usage-examples)

```json
{
  "model": "midjourney/v8.1/remove-background",
  "image": "https://example.com/product.png",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原图。高级参数为原图 URL 和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
