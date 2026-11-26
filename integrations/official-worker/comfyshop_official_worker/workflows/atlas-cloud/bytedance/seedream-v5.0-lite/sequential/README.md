# Seedream v5.0 Lite 连续生图

从同一段提示词生成一组相关图片。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-lite/sequential`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/sequential)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                    | 输入约定                                          |
| ---------------------- | ------------------------ | ---- | ----------------------------------------- | ------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v5.0-lite/sequential` | 工作机从执行配置读取                              |
| `prompt`               | `prompt`                 | 是   | 无                                        | 描述整组图片及各张内容。Atlas 建议英文少于 600 词 |
| `size`                 | `size`                   | 否   | `2048*2048`                               | 16 个 2K、3K 预设，使用 `宽*高` 像素格式          |
| `max_images`           | `max_images`             | 否   | 1                                         | 整数 1 至 15，指定成品数量上限                    |
| `output_format`        | `output_format`          | 否   | `jpeg`                                    | `jpeg` 或 `png`                                   |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                     | 输出 Base64 图片，由工作机解码保存                |

静态 Schema 的路径列为 `generateVideo` 和 `result`。工作机按官方端点文档和模型调用示例使用 `generateImage` 及 `prediction`。[官方端点文档](https://www.atlascloud.ai/docs/en/more-models/bytedance/seedream-v5.0-lite-sequential/generateImage) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-lite-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-lite-sequential.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-lite-sequential.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。

```json
{
  "model": "bytedance/seedream-v5.0-lite/sequential",
  "prompt": "画一组三张几何风格插图，分别呈现花园晨雾、午后和暮色，统一构图和线条。",
  "size": "2048*2048",
  "max_images": 3,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后工作机按 `data.outputs` 的顺序保存每张图片，可处理 URL 或 Base64。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/sequential#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、尺寸和最多生成张数位于默认区。格式和 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
