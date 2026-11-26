# Nano Banana 2 Lite Developer 图像编辑

依据提示词快速编辑参考图，以 1K 分辨率输出。 Atlas Cloud 模型 ID 为 `google/nano-banana-2-lite/edit-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2-lite/edit-developer)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                                     | 输入约定                                    |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------------------------ | ------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `google/nano-banana-2-lite/edit-developer` | 工作机从执行配置读取                        |
| `prompt`               | `prompt`                                             | 是   | 无                                         | 说明要修改的内容，可按顺序引用参考图        |
| `images`               | `reference_1` 至 `reference_14`、`reference_sources` | 是   | 无                                         | 1 至 14 张参考图，使用 HTTP(S) 图片地址     |
| `aspect_ratio`         | `aspect_ratio`                                       | 否   | `auto`                                     | Schema 的 15 个选项。自动模式由模型选择比例 |
| `resolution`           | `resolution`                                         | 否   | `1k`                                       | 仅 `1k`，工作流使用隐藏参数                 |
| `thinking_level`       | `thinking_level`                                     | 否   | `default`                                  | `default`、`high` 或 `minimal`              |
| `top_p`                | `top_p`                                              | 否   | 0.95                                       | 数值 0 至 1                                 |
| `temperature`          | `temperature`                                        | 否   | 1                                          | 数值 0 至 1                                 |
| `seed`                 | `seed`                                               | 否   | -1                                         | 整数。-1 使用随机种子                       |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                                      | 等待完成后从提交响应取结果                  |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                      | 返回 Base64 图片，由工作机解码保存          |

工作机将上传图片转换成 Atlas 素材地址，按编号发送，再按行追加文本区的公开图片地址。工作机提交 1K 分辨率。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-lite-edit-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-lite-edit-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-lite-edit-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2-lite/edit-developer#usage-examples)

```json
{
  "model": "google/nano-banana-2-lite/edit-developer",
  "prompt": "让参考图中的搪瓷水壶出现在木质料理台上，使用午后的自然光。",
  "images": ["https://example.com/kettle.jpg"],
  "aspect_ratio": "4:5",
  "resolution": "1k",
  "thinking_level": "minimal"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图与比例位于默认区。其他参考图、素材地址、思考、采样及响应方式位于高级区。分辨率预设为 1K。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
