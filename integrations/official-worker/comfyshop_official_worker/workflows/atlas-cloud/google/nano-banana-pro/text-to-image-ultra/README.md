# Nano Banana Pro Ultra 文生图

用文字生成 4K 或 8K 图片，可设置宽高比与输出格式。 Atlas Cloud 模型 ID 为 `google/nano-banana-pro/text-to-image-ultra`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-pro/text-to-image-ultra)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                       | 输入约定                           |
| ---------------------- | ------------------------ | ---- | -------------------------------------------- | ---------------------------------- |
| `model`                | `execution.config.model` | 是   | `google/nano-banana-pro/text-to-image-ultra` | 工作机从执行配置读取               |
| `prompt`               | `prompt`                 | 是   | 无                                           | 描述场景，精确文字用引号标记       |
| `aspect_ratio`         | `aspect_ratio`           | 否   | 由模型决定                                   | Schema 的 10 个比例预设            |
| `resolution`           | `resolution`             | 否   | `4k`                                         | `4k` 或 `8k`                       |
| `output_format`        | `output_format`          | 否   | `jpeg`                                       | `png` 或 `jpeg`                    |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                                        | 等待完成后从提交响应取结果         |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                        | 返回 Base64 图片，由工作机解码保存 |

比例选择模型默认时，工作机省略 `aspect_ratio`。工作机按 `outputs` 保存生成结果。Schema 在请求对象的属性定义外包含一个 `seed` 注记，官方参数表与请求示例均省略该字段。工作流采用请求对象声明的属性。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-pro-text-to-image-ultra.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-pro-text-to-image-ultra.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-pro-text-to-image-ultra.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-pro/text-to-image-ultra#usage-examples)

```json
{
  "model": "google/nano-banana-pro/text-to-image-ultra",
  "prompt": "为建筑双年展设计一张封面，标题「城市之间」，几何结构与白色留白清晰分层。",
  "aspect_ratio": "3:4",
  "resolution": "8k",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、比例、分辨率和格式位于默认区。两个响应方式选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
