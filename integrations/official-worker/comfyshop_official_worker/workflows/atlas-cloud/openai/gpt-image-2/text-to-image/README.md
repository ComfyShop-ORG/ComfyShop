# GPT Image 2 文生图

根据提示词生成图片，支持预设和自定义宽高。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                                                                                                        |
| ---------------------- | ------------------------ | ---- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `openai/gpt-image-2/text-to-image` | 工作机从执行配置读取                                                                                            |
| `prompt`               | `prompt`                 | 是   | 无                                 | 描述要生成的主体、构图与文字                                                                                    |
| `size`                 | `size`、`custom_size`    | 否   | `1024x1024`                        | 14 个 Atlas 尺寸预设或自定义 `宽x高`。每边至多 3840 且为 16 的倍数，总像素 655360 至 8294400，宽高比 1:3 至 3:1 |
| `quality`              | `quality`                | 否   | `medium`                           | `low`、`medium` 或 `high`                                                                                       |
| `output_format`        | `output_format`          | 否   | `jpeg`                             | `jpeg` 或 `png`                                                                                                 |
| `moderation`           | `moderation`             | 否   | `low`                              | Atlas 默认 `low`，OpenAI 定义为 `auto` 或 `low`                                                                 |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                              | 生成完成后从提交响应取结果                                                                                      |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                              | 返回 Base64 图片，由工作机解码保存                                                                              |

模型 API 和独立端点定义了实际请求字段。上游文档补充了自定义宽高的总像素范围与内容审核选项。模型页面的查询示例使用 `prediction`。[OpenAI 图像 API 参数](https://developers.openai.com/api/docs/guides/image-generation) · [官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/zh/more-models/openai/gpt-image-2-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2/text-to-image#usage-examples)

```json
{
  "model": "openai/gpt-image-2/text-to-image",
  "prompt": "设计一张城市骑行地图封面，浅灰底图、深绿色路线、角落留出文字区域。",
  "size": "1536x864",
  "quality": "medium",
  "output_format": "png",
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、质量、尺寸和格式位于默认区。自定义宽高、内容审核和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
