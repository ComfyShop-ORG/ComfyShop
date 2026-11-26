# Midjourney V8.1 风格迁移

按文字描述重绘一张图片，保留原图构图并产出 4 种变体。 Atlas Cloud 模型 ID 为 `midjourney/v8.1/style-transfer`。[官方模型 API](https://www.atlascloud.ai/models/midjourney/v8.1/style-transfer)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                        | 必填 | 默认值                           | 输入约定                          |
| ---------------------- | ------------------------------------- | ---- | -------------------------------- | --------------------------------- |
| `model`                | `execution.config.model`              | 是   | `midjourney/v8.1/style-transfer` | 工作机从执行配置读取              |
| `image`                | `input_image` 或 `input_image_source` | 是   | —                                | 上传原图或提供公开 HTTPS 图片地址 |
| `prompt`               | `prompt`                              | 是   | —                                | 描述目标画风、材质或光线          |
| `enable_base64_output` | `enable_base64_output`                | 否   | `false`                          | Base64 图片由工作机解码后保存     |

Atlas 每次任务返回四张风格变体，沿用原图构图。

[官方 Schema](https://static.atlascloud.ai/model/schema/midjourney-v8.1-style-transfer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/midjourney-v8.1-style-transfer.json) · [模型说明](https://static.atlascloud.ai/model/readme/midjourney-v8.1-style-transfer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/midjourney/v8.1/style-transfer#usage-examples)

```json
{
  "model": "midjourney/v8.1/style-transfer",
  "image": "https://example.com/landscape.png",
  "prompt": "保持原有构图，改用蓝绿色木刻版画风格。",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原图和目标风格。高级参数为原图 URL 和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
