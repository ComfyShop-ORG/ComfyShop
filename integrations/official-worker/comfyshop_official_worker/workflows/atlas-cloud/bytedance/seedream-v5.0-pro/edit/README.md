# Seedream v5.0 Pro 图像编辑

用提示词和参考图生成单张编辑结果。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-pro/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/edit)

## Atlas 接口参数

| Atlas 参数                 | ComfyShop 字段                                       | 必填 | 默认值                             | 输入约定                                                              |
| -------------------------- | ---------------------------------------------------- | ---- | ---------------------------------- | --------------------------------------------------------------------- |
| `model`                    | `execution.config.model`                             | 是   | `bytedance/seedream-v5.0-pro/edit` | 工作机从执行配置读取                                                  |
| `prompt`                   | `prompt`                                             | 是   | 无                                 | 描述编辑要求，可按提交顺序指明参考图，Atlas 建议英文提示词少于 600 词 |
| `images`                   | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                                 | 1 至 10 个图片 URL 或 Base64 data URL                                 |
| `size`                     | `size`                                               | 否   | `2048*2048`                        | Atlas Schema 的 14 个预设宽高，覆盖 1.5K 与 2K 档位                   |
| `output_format`            | `output_format`                                      | 否   | `jpeg`                             | `jpeg` 或 `png`                                                       |
| `background`               | `background`                                         | 否   | `opaque`                           | `opaque` 或 `transparent`。透明要求 PNG 输出及一张带透明通道的 PNG    |
| `thinking`                 | `thinking`                                           | 否   | `enabled`                          | `enabled` 或 `disabled`，控制深度思考                                 |
| `prompt_optimization_mode` | `prompt_optimization_mode`                           | 否   | `standard`                         | `standard` 或 `fast`，控制提示词优化方式                              |
| `enable_base64_output`     | `enable_base64_output`                               | 否   | false                              | 开启后在响应中返回 Base64 图片，工作机解码并保存                      |

表单支持直接上传 JPEG、PNG、WebP、BMP 和 GIF，工作机会将上传文件转换为 Atlas 素材 URL。高级区的素材输入按行接收公开的 HTTP(S) 地址或 Base64 data URL，也可用于提供 TIFF、HEIC、HEIF。混用时先按编号提交上传的图片，再按行提交文字区的素材，两者合计最多 10 张。输入 Base64 的文本字段上限为 4 MiB。透明模式会校验直接上传和内联的 PNG，远程链接由 Atlas 探测。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-pro-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-pro-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-pro-edit.md)

## API 调用

以下为透明背景示例。将 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。示例地址需换成带透明通道的 PNG。

```json
{
  "model": "bytedance/seedream-v5.0-pro/edit",
  "prompt": "将花瓶的配色换为深蓝与白色，保持轮廓和透明背景。",
  "images": ["https://example.com/reference-with-alpha.png"],
  "size": "1536*1536",
  "output_format": "png",
  "background": "transparent"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 下载图片，或解码 Base64 图片。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/edit#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图与尺寸位于默认区。剩余参考图、素材地址、背景与输出选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
