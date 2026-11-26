# Seedream v5.5 文生图

按提示词生成单张图片，可直接生成带 Alpha 通道的透明 PNG。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.5/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                  | 输入约定                                                         |
| ---------------------- | ------------------------ | ---- | --------------------------------------- | ---------------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v5.5/text-to-image` | 工作机从执行配置读取                                             |
| `prompt`               | `prompt`                 | 是   | 无                                      | 描述画面，建议不超过 300 个中文字符或 600 个英文单词             |
| `size`                 | `size`                   | 否   | `2048*2048`                             | 24 个 1K、1.5K、2K 宽高预设，总像素范围 921600 至 4624220        |
| `output_format`        | `output_format`          | 否   | `png`                                   | `png` 或 `jpeg`                                                  |
| `background`           | `background`             | 否   | `auto`                                  | `auto`、`transparent` 或 `opaque`。透明要求 PNG，JPEG 始终不透明 |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                   | 等待生成完成后在提交响应中取结果                                 |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                   | 返回 Base64 图片，工作机解码保存                                 |

Atlas 在 `image_results` 中按 `outputs` 的索引返回实际背景类型。工作机保留图片原件，并将该数组保存成 JSON 成品。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.5-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.5-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.5-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.5/text-to-image#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.5/text-to-image",
  "prompt": "一枝线条清晰的半透明水彩银杏叶，孤立摆放，背景透明。",
  "size": "1536*1536",
  "output_format": "png",
  "background": "transparent",
  "enable_sync_mode": false,
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。输出格式、背景和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
