# GPT Image 1 Mini 图像编辑

用提示词编辑最多四张参考图，可选尺寸、画质和响应方式。 Atlas Cloud 模型 ID 为 `openai/gpt-image-1-mini/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-1-mini/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                      | 必填 | 默认值                         | 输入约定                                |
| ---------------------- | --------------------------------------------------- | ---- | ------------------------------ | --------------------------------------- |
| `model`                | `execution.config.model`                            | 是   | `openai/gpt-image-1-mini/edit` | 工作机从执行配置读取                    |
| `prompt`               | `prompt`                                            | 是   | 无                             | 指明需要修改和保留的内容                |
| `images`               | `reference_1` 至 `reference_4`、`reference_sources` | 是   | 无                             | 1 至 4 张参考图                         |
| `quality`              | `quality`                                           | 否   | `medium`                       | `high`、`medium` 或 `low`               |
| `size`                 | `size`                                              | 否   | `1024x1024`                    | `1024x1024`、`1024x1536` 或 `1536x1024` |
| `enable_sync_mode`     | `enable_sync_mode`                                  | 否   | false                          | 完成后从提交响应取成品                  |
| `enable_base64_output` | `enable_base64_output`                              | 否   | false                          | 返回 Base64 图片，工作机解码保存        |

上传图按编号提交，再追加文本区的公开 HTTP(S) 地址或 Base64 data URL。文本字段上限为 4 MiB。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-1-mini-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-1-mini-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-1-mini-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址换成实际素材。[官方端点文档](https://www.atlascloud.ai/docs/zh/more-models/openai/gpt-image-1-mini-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-1-mini/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-1-mini/edit",
  "prompt": "将参考图转换成双色剪纸风格，保留屋檐和人物的轮廓。",
  "images": ["https://example.com/street.jpg"],
  "size": "1024x1536",
  "quality": "high"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、画质和尺寸位于默认区。其余参考图、来源地址和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
