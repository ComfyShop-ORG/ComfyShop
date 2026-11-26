# Nano Banana 2 Lite 文生图

从提示词快速生成 1K 图片，可选择不同比例和思考档位。 Atlas Cloud 模型 ID 为 `google/nano-banana-2-lite/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2-lite/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                    | 输入约定                                |
| ---------------------- | ------------------------ | ---- | ----------------------------------------- | --------------------------------------- |
| `model`                | `execution.config.model` | 是   | `google/nano-banana-2-lite/text-to-image` | 工作机从执行配置读取                    |
| `prompt`               | `prompt`                 | 是   | 无                                        | 描述场景，精确文字用引号标记            |
| `aspect_ratio`         | `aspect_ratio`           | 否   | `auto`                                    | Schema 的 15 个选项。自动模式生成方形图 |
| `resolution`           | `resolution`             | 否   | `1k`                                      | 仅 `1k`，工作流使用隐藏参数             |
| `thinking_level`       | `thinking_level`         | 否   | `default`                                 | `default`、`high` 或 `minimal`          |
| `top_p`                | `top_p`                  | 否   | 0.95                                      | 数值 0 至 1                             |
| `temperature`          | `temperature`            | 否   | 1                                         | 数值 0 至 1                             |
| `seed`                 | `seed`                   | 否   | -1                                        | 整数。-1 使用随机种子                   |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                     | 等待完成后从提交响应取结果              |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                     | 返回 Base64 图片，由工作机解码保存      |

工作机提交 1K 分辨率。`outputs` 用于保存成品图片。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-lite-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-lite-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-lite-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2-lite/text-to-image#usage-examples)

```json
{
  "model": "google/nano-banana-2-lite/text-to-image",
  "prompt": "一张简洁的冬日树林插画，蓝灰色树影和雪地，用横向大留白构图。",
  "aspect_ratio": "21:9",
  "resolution": "1k",
  "thinking_level": "minimal"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与比例位于默认区。思考、采样、种子及响应方式位于高级区。分辨率预设为 1K。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
