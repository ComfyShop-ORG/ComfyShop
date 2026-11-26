# Grok Imagine Image Quality 图像编辑

根据提示词编辑一张或多张图片，最多输出四张。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-image-quality/edit`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-image-quality/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                        | 必填 | 默认值                                | 输入约定                                                                                                    |
| ---------------------- | ----------------------------------------------------- | ---- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                              | 是   | `xai/grok-imagine-image-quality/edit` | 工作机从执行配置读取                                                                                        |
| `prompt`               | `prompt`                                              | 是   | 官方可编辑示例                        | 用 `<IMAGE_0>`、`<IMAGE_1>` 等引用多张源图                                                                  |
| `image_urls`           | `source_image_1` 至 `source_image_8`，`image_sources` | 是   | —                                     | 1 至 8 张图片，接受公开 URL 或 Base64 Data URI                                                              |
| `num_images`           | `num_images`                                          | 否   | `1`                                   | 整数 1 至 4，Atlas 按张计费                                                                                 |
| `aspect_ratio`         | `aspect_ratio`                                        | 否   | `auto`                                | `auto`、`1:1`、`3:4`、`4:3`、`9:16`、`16:9`、`2:3`、`3:2`、`9:19.5`、`19.5:9`、`9:20`、`20:9`、`1:2`、`2:1` |
| `resolution`           | `resolution`                                          | 否   | `1k`                                  | `1k` 或 `2k`，方形图标称 1024×1024 或 2048×2048                                                             |
| `enable_base64_output` | `enable_base64_output`                                | 否   | `false`                               | 开启后返回 Base64                                                                                           |

图片输入支持上传及外部来源。外部来源每行一个，按上传槽位在前、外部来源在后的顺序组成 `image_urls`。上传或 Data URI 支持 PNG、JPEG、WebP。Data URI 过大时可直接上传。只有一张源图时结果沿用原图宽高比。Atlas 分别按张对源图和输出计费。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-image-quality-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-image-quality-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/xai-grok-imagine-image-quality-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/xai/grok-imagine-image-quality-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-image-quality/edit#usage-examples)

```json
{
  "model": "xai/grok-imagine-image-quality/edit",
  "prompt": "Render this as a pencil sketch with detailed shading.",
  "image_urls": ["https://example.com/source.png"],
  "num_images": 1,
  "aspect_ratio": "auto",
  "resolution": "1k",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、第一张源图、出图数量、画面比例和分辨率。高级参数为额外源图、外部来源和 Base64 输出。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
