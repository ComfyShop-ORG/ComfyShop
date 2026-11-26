# GPT Image 1.5 文生图

从提示词生成静态图片，可选择三种尺寸、三档画质及 JPEG 或 PNG。 Atlas Cloud 模型 ID 为 `openai/gpt-image-1.5/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-1.5/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                |
| ---------------------- | ------------------------ | ---- | ------------------------------------ | --------------------------------------- |
| `model`                | `execution.config.model` | 是   | `openai/gpt-image-1.5/text-to-image` | 工作机从执行配置读取                    |
| `prompt`               | `prompt`                 | 是   | 无                                   | 描述图像内容                            |
| `size`                 | `size`                   | 否   | `1024x1024`                          | `1024x1024`、`1024x1536` 或 `1536x1024` |
| `quality`              | `quality`                | 否   | `medium`                             | `low`、`medium` 或 `high`               |
| `output_format`        | `output_format`          | 否   | `jpeg`                               | `jpeg` 或 `png`                         |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                | 等待完成后从提交响应取结果              |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                | 返回 Base64 图片，由工作机解码保存      |

请求字段使用本模型的 Atlas Schema 和独立端点定义。模型调用示例通过 `prediction` 查询。[官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-1.5-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-1.5-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-1.5-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/ja/more-models/openai/gpt-image-1.5-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-1.5/text-to-image#usage-examples)

```json
{
  "model": "openai/gpt-image-1.5/text-to-image",
  "prompt": "一幅描绘雨后旧书店橱窗的插画，暖黄室内光、简洁构图、印刷纹理。",
  "size": "1024x1536",
  "quality": "medium",
  "output_format": "png",
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、质量、尺寸和格式位于默认区。同步与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
