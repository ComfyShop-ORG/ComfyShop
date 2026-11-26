# Seedream v5.0 Flash 图像编辑

用提示词和一组参考图生成单张编辑结果，可选择透明背景。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-flash/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-flash/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                               | 输入约定                                                                            |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------------------ | ----------------------------------------------------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v5.0-flash/edit` | 工作机从执行配置读取                                                                |
| `prompt`               | `prompt`                                             | 是   | 无                                   | 写明修改内容，Atlas 建议英文提示词少于 600 词                                       |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                                   | 1 至 10 个 URL 或 Base64 data URL，支持 JPEG、PNG、WebP、BMP、TIFF、GIF、HEIC、HEIF |
| `size`                 | `size`                                               | 否   | `2048*2048`                          | 请求 Schema 的 16 个 1.5K、2K 宽高预设                                              |
| `output_format`        | `output_format`                                      | 否   | `jpeg`                               | `jpeg` 或 `png`                                                                     |
| `background`           | `background`                                         | 否   | `opaque`                             | `opaque` 或 `transparent`。透明输出要求 PNG 格式与一张带 Alpha 通道的 PNG           |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                | 开启后返回 Base64 图片，工作机解码保存                                              |

工作机将上传文件转为素材 URL，然后按行追加公开 HTTP(S) 地址或 Base64 data URL。TIFF、HEIC、HEIF 可由文本区提供，字段上限为 4 MiB。透明模式检查直接上传和内联的 PNG，远程链接由 Atlas 校验。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-flash-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-flash-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-flash-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。以下为透明背景示例，将地址替换为一张带 Alpha 通道的 PNG。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-flash/edit#usage-examples)

```json
{
  "model": "bytedance/seedream-v5.0-flash/edit",
  "prompt": "把这张产品图中的灯罩改为浅灰亚麻，保留灯具结构与透明背景。",
  "images": ["https://example.com/translucent-lamp.png"],
  "size": "1536*1536",
  "output_format": "png",
  "background": "transparent",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图与尺寸位于默认区。其余参考图、素材地址、格式、背景和 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
