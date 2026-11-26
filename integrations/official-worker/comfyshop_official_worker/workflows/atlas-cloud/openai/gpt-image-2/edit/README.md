# GPT Image 2 图像编辑

按提示词编辑一张或多张参考图，支持成品宽高、画质和格式设置。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                    | 输入约定                                                                                                        |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `openai/gpt-image-2/edit` | 工作机从执行配置读取                                                                                            |
| `prompt`               | `prompt`                                             | 是   | 无                        | 说明要修改或保留的内容                                                                                          |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                        | 1 至 10 张参考图，上传图按编号提交，随后追加文本区的素材                                                        |
| `size`                 | `size`、`custom_size`                                | 否   | `1024x1024`               | 14 个 Atlas 尺寸预设或自定义 `宽x高`。每边至多 3840 且为 16 的倍数，总像素 655360 至 8294400，宽高比 1:3 至 3:1 |
| `quality`              | `quality`                                            | 否   | `medium`                  | `low`、`medium` 或 `high`                                                                                       |
| `output_format`        | `output_format`                                      | 否   | `jpeg`                    | `jpeg` 或 `png`                                                                                                 |
| `moderation`           | `moderation`                                         | 否   | `low`                     | Atlas 默认 `low`，OpenAI 定义 `auto` 与 `low`                                                                   |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                     | 生成完成后从提交响应取结果                                                                                      |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                     | 返回 Base64 图片，由工作机解码保存                                                                              |

上传素材使用 JPEG 或 PNG，工作机将原件上传到 Atlas 后发送素材地址。文本区可填写公开地址或 Base64 data URL，上限为 4 MiB。尺寸及审核选项依据 OpenAI 图像文档，轮询地址使用模型 API 调用示例。[OpenAI 图像 API 参数](https://developers.openai.com/api/docs/guides/image-generation) · [官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址换成实际图片。[官方端点文档](https://www.atlascloud.ai/docs/ko/more-models/openai/gpt-image-2-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-2/edit",
  "prompt": "保留咖啡杯的外形和印字，将原图背景换成深蓝色的纸面，柔和侧光。",
  "images": ["https://example.com/cup.jpg"],
  "size": "1536x864",
  "quality": "medium",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、质量、尺寸及格式位于默认区。其余参考图、地址、自定义宽高、审核及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
