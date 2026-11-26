# Seedream v5.0 Pro 文生图

根据提示词生成单张图片，提供 1.5K 和 2K 的预设尺寸以及可选的提示词优化方式。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-pro/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/text-to-image)

## Atlas 接口参数

| Atlas 参数                 | ComfyShop 字段             | 必填 | 默认值                                      | 输入约定                                                |
| -------------------------- | -------------------------- | ---- | ------------------------------------------- | ------------------------------------------------------- |
| `model`                    | `execution.config.model`   | 是   | `bytedance/seedream-v5.0-pro/text-to-image` | 工作机从执行配置读取                                    |
| `prompt`                   | `prompt`                   | 是   | 无                                          | 描述要生成的图片，Atlas 建议英文提示词少于 600 词       |
| `size`                     | `size`                     | 否   | `2048*2048`                                 | 表单列出 Atlas Schema 的 14 种预设，使用 `宽*高` 像素值 |
| `output_format`            | `output_format`            | 否   | `jpeg`                                      | `jpeg` 或 `png`                                         |
| `thinking`                 | `thinking`                 | 否   | `enabled`                                   | `enabled` 或 `disabled`，控制深度思考                   |
| `prompt_optimization_mode` | `prompt_optimization_mode` | 否   | `standard`                                  | `standard` 侧重优化质量，`fast` 缩短优化时间            |
| `enable_base64_output`     | `enable_base64_output`     | 否   | false                                       | 开启后在响应中返回 Base64 图片，工作机解码并保存        |

尺寸按 Atlas 的 1.5K 与 2K 档位提供。缩短生成时间时，可同时设置 `thinking: "disabled"` 和 `prompt_optimization_mode: "fast"`。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-pro-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-pro-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-pro-text-to-image.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seedream-v5.0-pro/text-to-image",
  "prompt": "玻璃温室内的白色山茶特写，清晨的柔光，深绿色背景。",
  "size": "1536*1536",
  "output_format": "png",
  "thinking": "disabled",
  "prompt_optimization_mode": "fast",
  "enable_base64_output": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载图片或解码 Base64。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/text-to-image#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。格式、思考、优化和输出方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
