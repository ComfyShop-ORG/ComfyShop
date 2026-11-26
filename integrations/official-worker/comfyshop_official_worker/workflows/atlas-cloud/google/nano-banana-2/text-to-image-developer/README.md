# Nano Banana 2 Developer 文生图

用提示词生成图片，可调整分辨率、思考档位和网页搜索。 Atlas Cloud 模型 ID 为 `google/nano-banana-2/text-to-image-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2/text-to-image-developer)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                         | 输入约定                           |
| ---------------------- | ------------------------ | ---- | ---------------------------------------------- | ---------------------------------- |
| `model`                | `execution.config.model` | 是   | `google/nano-banana-2/text-to-image-developer` | 工作机从执行配置读取               |
| `prompt`               | `prompt`                 | 是   | 无                                             | 描述场景，精确文字用引号标记       |
| `aspect_ratio`         | `aspect_ratio`           | 否   | 由模型决定                                     | Schema 的 10 个比例预设            |
| `resolution`           | `resolution`             | 否   | `1k`                                           | `1k`、`2k` 或 `4k`                 |
| `thinking_level`       | `thinking_level`         | 否   | `default`                                      | `default`、`high` 或 `minimal`     |
| `enable_web_search`    | `enable_web_search`      | 否   | false                                          | 使用 Google 网页搜索补充实时信息   |
| `top_p`                | `top_p`                  | 否   | 0.95                                           | 数值 0 至 1                        |
| `temperature`          | `temperature`            | 否   | 1                                              | 数值 0 至 1                        |
| `seed`                 | `seed`                   | 否   | -1                                             | 整数。-1 使用随机种子              |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                          | 等待完成后从提交响应取结果         |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                          | 返回 Base64 图片，由工作机解码保存 |

比例选择模型默认时，工作机省略 `aspect_ratio`。静态示例含 `output_format`，本接口的请求 Schema 列出上表字段。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-text-to-image-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-text-to-image-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-text-to-image-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2/text-to-image-developer#usage-examples)

```json
{
  "model": "google/nano-banana-2/text-to-image-developer",
  "prompt": "设计一个简洁的航海科普插图，蓝色海浪和白色小帆船，画面保留宽阔天空。",
  "aspect_ratio": "16:9",
  "resolution": "2k",
  "thinking_level": "minimal",
  "enable_web_search": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、比例及分辨率位于默认区。思考、网页搜索、采样、种子及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
