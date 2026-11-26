# GPT Image 1.5 图像编辑

依据提示词编辑参考图，提供源图细节保真度、成品画质和三种尺寸。 Atlas Cloud 模型 ID 为 `openai/gpt-image-1.5/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-1.5/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                      | 输入约定                                  |
| ---------------------- | ---------------------------------------------------- | ---- | --------------------------- | ----------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `openai/gpt-image-1.5/edit` | 工作机从执行配置读取                      |
| `prompt`               | `prompt`                                             | 是   | 无                          | 说明要修改及保留的部分                    |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                          | 1 至 10 张参考图                          |
| `size`                 | `size`                                               | 否   | `1024x1024`                 | `1024x1024`、`1024x1536` 或 `1536x1024`   |
| `quality`              | `quality`                                            | 否   | `medium`                    | `low`、`medium` 或 `high`                 |
| `input_fidelity`       | `input_fidelity`                                     | 否   | `high`                      | `low` 或 `high`，影响参考图细节的保留程度 |
| `output_format`        | `output_format`                                      | 否   | `jpeg`                      | `jpeg` 或 `png`                           |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                       | 等待完成后从提交响应取结果                |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                       | 返回 Base64 图片，由工作机解码保存        |

工作机将上传的 JPEG 或 PNG 转成素材 URL，按编号发送，随后按行追加公开 URL 或 Base64 data URL。文本字段上限为 4 MiB。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-1.5-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-1.5-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-1.5-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例图片地址换成实际素材。[官方端点文档](https://www.atlascloud.ai/docs/it/more-models/openai/gpt-image-1.5-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-1.5/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-1.5/edit",
  "prompt": "把茶叶包装放在浅色石桌上，保留包装原有文字、图案和比例，改用柔和的窗光。",
  "images": ["https://example.com/tea-box.jpg"],
  "size": "1536x1024",
  "input_fidelity": "high",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、质量、尺寸和格式位于默认区。其余参考图、素材地址、输入保真度及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
