# Ideogram v4 Quality 文生图

用提示词生成图片，支持多种横竖构图和 JPEG、PNG 输出。 Atlas Cloud 模型 ID 为 `ideogram/v4/quality/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/ideogram/v4/quality/text-to-image)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                              | 输入约定                                                                                  |
| --------------- | ------------------------ | ---- | ----------------------------------- | ----------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `ideogram/v4/quality/text-to-image` | 工作机从执行配置读取                                                                      |
| `prompt`        | `prompt`                 | 是   | —                                   | 最多 2,000 字符                                                                           |
| `image_size`    | `size_preset`            | 否   | `landscape_16_9`                    | `square_hd`、`square`、`portrait_3_4`、`portrait_9_16`、`landscape_4_3`、`landscape_16_9` |
| `output_format` | `output_format`          | 否   | `jpeg`                              | `jpeg` 或 `png`                                                                           |
| `seed`          | `seed`                   | 否   | 随机                                | 非负整数                                                                                  |

公开端点将 `image_size` 声明为六项预设。Schema 中的 `x-atlas` 尺寸元数据没有声明自定义请求结构。

[官方 Schema](https://static.atlascloud.ai/model/schema/ideogram-v4-quality-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/ideogram-v4-quality-text-to-image.json)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/ideogram/v4-quality-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/ideogram/v4/quality/text-to-image#usage-examples)

```json
{
  "model": "ideogram/v4/quality/text-to-image",
  "prompt": "一株垂柳在日出时分的湖边，水面如镜。",
  "image_size": "landscape_16_9",
  "output_format": "jpeg"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词、尺寸预设和输出格式。高级参数为随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../../docs/deployment.md#官方工作机)
