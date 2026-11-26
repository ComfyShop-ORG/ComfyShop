# Seedream v5.0 Lite 图像编辑

用提示词和参考图生成一张编辑结果。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-lite/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                              | 输入约定                                                                |
| ---------------------- | ---------------------------------------------------- | ---- | ----------------------------------- | ----------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v5.0-lite/edit` | 工作机从执行配置读取                                                    |
| `prompt`               | `prompt`                                             | 是   | 无                                  | 写明编辑要求，可按提交顺序引用参考图。Atlas 建议英文少于 600 词         |
| `images`               | `reference_1` 至 `reference_14`、`reference_sources` | 是   | 无                                  | 1 至 14 个 URL 或 Base64 data URL，支持 JPEG、PNG、WebP、BMP、TIFF、GIF |
| `size`                 | `size`                                               | 否   | `2048*2048`                         | 16 个 2K、3K 预设，使用 `宽*高` 像素格式                                |
| `output_format`        | `output_format`                                      | 否   | `jpeg`                              | `jpeg` 或 `png`                                                         |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                               | 输出 Base64 图片，由工作机解码保存                                      |

工作机将直接上传的 JPEG、PNG、WebP、BMP、GIF 转成素材 URL。高级区按行接收公开 HTTP(S) 地址或 Base64 data URL，也可提供 TIFF。工作机先按编号提交上传文件，再按文本行序提交地址。Base64 文本字段上限为 4 MiB。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-lite-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-lite-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-lite-edit.md)

## API 调用

用 `Authorization: Bearer <API_KEY>` 将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，将示例地址换成可公开访问的素材。静态 Schema 路径列为 `generateVideo` 和 `result`。工作机采用模型调用示例的 `generateImage` 和 `prediction`。[官方端点文档](https://www.atlascloud.ai/docs/zh/more-models/bytedance/seedream-v5.0-lite-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/edit#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.0-lite/edit",
  "prompt": "保留手工陶碗的形状和边缘纹理，将釉面换成浅绿色。",
  "images": ["https://example.com/bowl.jpg"],
  "size": "2048*2048",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载图片或解码 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图和尺寸位于默认区。其他参考图、素材地址和输出选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
