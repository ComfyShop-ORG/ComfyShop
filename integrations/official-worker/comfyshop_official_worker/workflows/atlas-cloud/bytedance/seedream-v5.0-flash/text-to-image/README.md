# Seedream v5.0 Flash 文生图

从提示词快速生成单张图像，支持 1.5K、2K 及两种输出格式。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-flash/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-flash/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                        | 输入约定                                        |
| ---------------------- | ------------------------ | ---- | --------------------------------------------- | ----------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v5.0-flash/text-to-image` | 工作机从执行配置读取                            |
| `prompt`               | `prompt`                 | 是   | 无                                            | 描述主体和画面。Atlas 建议英文提示词少于 600 词 |
| `size`                 | `size`                   | 否   | `2048*2048`                                   | 请求 Schema 中的 16 个 1.5K、2K 宽高预设        |
| `output_format`        | `output_format`          | 否   | `jpeg`                                        | `jpeg` 或 `png`                                 |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                         | 开启后返回 Base64 图片，工作机解码保存          |

模型简介还提到 1K 与部分自定义尺寸能力。表单采用 Atlas 请求 Schema 明确列出的尺寸枚举。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-flash-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-flash-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-flash-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-flash/text-to-image#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.0-flash/text-to-image",
  "prompt": "设计一张横版咖啡店开业插画，深蓝底色、暖黄色窗光和手写笔触，右侧留白。",
  "size": "2816*1584",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。输出格式与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
