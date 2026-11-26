# GPT Image 1 Mini 文生图

从提示词生成一张或多张静态图片，并可设置 JPEG 输出的压缩值。 Atlas Cloud 模型 ID 为 `openai/gpt-image-1-mini/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-1-mini/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                  | 输入约定                                |
| ---------------------- | ------------------------ | ---- | --------------------------------------- | --------------------------------------- |
| `model`                | `execution.config.model` | 是   | `openai/gpt-image-1-mini/text-to-image` | 工作机从执行配置读取                    |
| `prompt`               | `prompt`                 | 是   | 无                                      | 描述要生成的图像                        |
| `size`                 | `size`                   | 否   | `1024x1024`                             | `1024x1024`、`1024x1536` 或 `1536x1024` |
| `quality`              | `quality`                | 否   | `medium`                                | `low`、`medium` 或 `high`               |
| `output_format`        | `output_format`          | 否   | `png`                                   | `png` 或 `jpeg`                         |
| `output_compression`   | `output_compression`     | 否   | 100                                     | JPEG 输出时发送，整数 0 至 100          |
| `n`                    | `n`                      | 否   | 1                                       | 整数 1 至 10，指定成品数量              |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                   | 完成后从提交响应直接取结果              |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                   | 返回 Base64 图片，工作机解码保存        |

工作机按输出格式发送压缩参数。PNG 成品使用接口默认编码。[OpenAI 输出格式](https://developers.openai.com/api/docs/guides/image-generation) · [官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-1-mini-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-1-mini-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-1-mini-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/zh/more-models/openai/gpt-image-1-mini-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-1-mini/text-to-image#usage-examples)

```json
{
  "model": "openai/gpt-image-1-mini/text-to-image",
  "prompt": "绘制三张同色系的陶瓷杯产品照片，简洁的暖灰背景，柔和漫射光。",
  "size": "1024x1024",
  "quality": "medium",
  "output_format": "jpeg",
  "output_compression": 85,
  "n": 3
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、质量、尺寸、格式和数量位于默认区。压缩、同步与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
