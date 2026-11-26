# Seedream v5.0 Lite 文生图

根据提示词生成单张图片，提供 2K 与 3K 尺寸预设。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-lite`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                         | 输入约定                                                 |
| ---------------------- | ------------------------ | ---- | ------------------------------ | -------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v5.0-lite` | 工作机从执行配置读取                                     |
| `prompt`               | `prompt`                 | 是   | 无                             | 描述要生成的图片，Atlas 建议英文提示词少于 600 词        |
| `size`                 | `size`                   | 否   | `2048*2048`                    | Atlas Schema 的 16 个 2K、3K 预设，使用 `宽*高` 像素格式 |
| `output_format`        | `output_format`          | 否   | `jpeg`                         | `jpeg` 或 `png`                                          |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                          | 开启后返回 Base64 图片，工作机解码保存                   |

静态 Schema 的路径栏写为 `generateVideo` 和 `result`。模型 API 页和独立端点文档给出 `generateImage`，模型 API 页指定用 `prediction` 查询。工作机按模型页和端点文档调用。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v5.0-lite/generateImage) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-lite.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-lite.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seedream-v5.0-lite",
  "prompt": "方形城市植物展海报，用清晰的中文标题「城市植物」和三种叶片插画。",
  "size": "3072*3072",
  "output_format": "png",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载图片或解码 Base64。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。格式与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
