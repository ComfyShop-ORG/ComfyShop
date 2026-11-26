# Seedream v5.0 Lite 连续图像编辑

用提示词和可选参考图生成一组相关的图片。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-lite/edit-sequential`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/edit-sequential)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                                         | 输入约定                                                                                          |
| ---------------------- | ---------------------------------------------------- | ---- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v5.0-lite/edit-sequential` | 工作机从执行配置读取                                                                              |
| `prompt`               | `prompt`                                             | 是   | 无                                             | 描述整组编辑要求。Atlas 建议英文少于 600 词                                                       |
| `images`               | `reference_1` 至 `reference_14`、`reference_sources` | 否   | 无                                             | 省略时只用提示词。提供时为 1 至 14 个 JPEG、PNG、WebP、BMP、TIFF 或 GIF 的 URL 或 Base64 data URL |
| `size`                 | `size`                                               | 否   | `2048*2048`                                    | 16 个 2K、3K 预设，使用 `宽*高` 像素格式                                                          |
| `max_images`           | `max_images`                                         | 否   | 1                                              | 成品张数上限，整数 1 至 15。与参考图张数合计不能超过 15                                           |
| `output_format`        | `output_format`                                      | 否   | `jpeg`                                         | `jpeg` 或 `png`                                                                                   |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                          | 输出 Base64 图片，由工作机解码保存                                                                |

工作机将直接上传的 JPEG、PNG、WebP、BMP、GIF 转成素材 URL。高级区按行接收公开 HTTP(S) 地址或 Base64 data URL，也可提供 TIFF。按编号发送上传文件，再按行发送地址，工作机在上传到 Atlas 前校验张数。Base64 文本字段上限为 4 MiB。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-lite-edit-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-lite-edit-sequential.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-lite-edit-sequential.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。静态 Schema 中的路径显示为 `generateVideo` 和 `result`，工作机依据端点文档和模型调用示例选择 `generateImage` 及 `prediction`。[官方端点文档](https://www.atlascloud.ai/docs/en/more-models/bytedance/seedream-v5.0-lite-edit-sequential/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-lite/edit-sequential#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.0-lite/edit-sequential",
  "prompt": "保留茶具的造型，分别生成暖白、松绿和深蓝釉色的三张成品图。",
  "images": ["https://example.com/tea-set.jpg"],
  "size": "2048*2048",
  "max_images": 3,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存每张图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、尺寸和最多生成张数位于默认区。其他参考图、素材地址和输出选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
