# MAI-Image 2.5 Flash 图片编辑

根据提示词编辑一张图片。 Atlas Cloud 模型 ID 为 `microsoft/mai-image-2.5-flash/edit`。[官方模型 API](https://www.atlascloud.ai/models/microsoft/mai-image-2.5-flash/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                        | 必填 | 默认值                               | 输入约定                                   |
| ---------------------- | ------------------------------------- | ---- | ------------------------------------ | ------------------------------------------ |
| `model`                | `execution.config.model`              | 是   | `microsoft/mai-image-2.5-flash/edit` | 工作机从执行配置读取                       |
| `image`                | `input_image` 或 `input_image_source` | 是   | —                                    | 一张 JPEG 或 PNG，可上传、填 URL 或 Base64 |
| `prompt`               | `prompt`                              | 是   | —                                    | 编辑要求，Atlas 上下文上限为 32,000 个令牌 |
| `enable_base64_output` | `enable_base64_output`                | 否   | `false`                              | Base64 结果由工作机解码后保存              |
| `enable_sync_mode`     | `enable_sync_mode`                    | 否   | `false`                              | 在提交响应中等待并取成品                   |

原图总像素须小于 1,376,256。工作机校验已上传图像的像素总数，Atlas 校验外部素材与令牌上限。

[官方 Schema](https://static.atlascloud.ai/model/schema/microsoft-mai-image-2.5-flash-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/microsoft-mai-image-2.5-flash-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/microsoft-mai-image-2.5-flash-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/microsoft/mai-image-2.5-flash-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/microsoft/mai-image-2.5-flash/edit#usage-examples)

```json
{
  "model": "microsoft/mai-image-2.5-flash/edit",
  "image": "https://example.com/source.png",
  "prompt": "保留主体位置，将画面转为木刻插画。",
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

开启同步且提交已返回成品时，工作机直接保存。异步时从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原图和提示词。高级参数为原图来源、Base64 成品和同步返回。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
