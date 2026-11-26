# GPT Image 2.6 Sunburst 图像编辑

用提示词与参考图编辑图片，也可将参考图变为循环 GIF。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2.6-sunburst/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2.6-sunburst/edit)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                                       | 必填 | 默认值                               | 输入约定                                                                                           |
| ------------------- | ---------------------------------------------------- | ---- | ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `model`             | `execution.config.model`                             | 是   | `openai/gpt-image-2.6-sunburst/edit` | 工作机从执行配置读取                                                                               |
| `prompt`            | `prompt`                                             | 是   | 官方英文礼篮示例                     | 最多 32000 字符，描述编辑目标                                                                      |
| `images`            | `reference_1` 至 `reference_16`、`reference_sources` | 是   | 无                                   | 1 至 16 个公开 URL、Base64 data URL 或 Atlas `asset://ID` 引用。上传槽位按编号列在前面             |
| `mask`              | `mask` 或 `mask_source`                              | 否   | 无                                   | 作用于第一张图的带透明通道 PNG。透明区域是编辑范围，须与首图同尺寸。与 `markup` 互斥，GIF 禁用     |
| `markup`            | `markup` 或 `markup_source`                          | 否   | 无                                   | 作用于第一张图的透明 PNG 标注，方向归一后须与首图同尺寸，最多 16777216 像素和 50 MB。可与 GIF 同用 |
| `quality`           | `quality`                                            | 否   | `medium`                             | `auto`、`low`、`medium`、`high`、`xhigh`、`max`                                                    |
| `complexity`        | `complexity`                                         | 否   | `high`                               | `low`、`medium` 或 `high`，控制规划深度                                                            |
| `size`              | `size`、`custom_size`                                | 否   | 静态 `1024x1024`，GIF `auto`         | 预设或 `宽x高`。每边 256 至 3840 且为 16 的倍数，总像素最多 8294400，宽高比 1:3 至 3:1             |
| `background`        | `background`                                         | 否   | `auto`                               | `auto`、`opaque`、`transparent`。透明要求 PNG 或 WebP                                              |
| `output_format`     | `output_format`                                      | 否   | `png`                                | `png`、`jpeg`、`webp` 或 `gif`                                                                     |
| `frame_count`       | `frame_count`                                        | 否   | 9                                    | 仅 GIF，整数 2 至 64                                                                               |
| `frame_duration_ms` | `frame_duration_ms`                                  | 否   | 200                                  | 仅 GIF，整数 20 至 2000 毫秒，Atlas 按 10 毫秒取整                                                 |
| `moderation`        | `moderation`                                         | 否   | `auto`                               | `auto` 或 `low`                                                                                    |
| `n`                 | `n`                                                  | 否   | 1                                    | 整数 1 至 10                                                                                       |

来源文本区每个字段最多 4 MiB。`asset://ID` 由 Atlas 解析，使用官方工作机 Atlas 账号已有权限的素材。上传蒙版使用 PNG 且文件小于 4 MB。标注和蒙版的可编辑区域以及按方向修正后的尺寸由 Atlas 最终校验。GIF 的尺寸指单帧，Atlas 还校验多帧合成后的总尺寸。[Atlas 素材库](https://www.atlascloud.ai/blog/guides/atlas-cloud-asset-library-seedance-2-0) · [OpenAI 蒙版接口格式](https://developers.openai.com/api/reference/python/resources/images/methods/edit) · [官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2.6-sunburst-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2.6-sunburst-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2.6-sunburst-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例链接换成实际素材。[官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2.6-sunburst/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-2.6-sunburst/edit",
  "prompt": "将圈出的杯柄换成浅蓝色，保持杯身材质、位置和背景。",
  "images": ["https://example.com/ceramic-cup.jpg"],
  "markup": "https://example.com/cup-markup.png",
  "output_format": "png",
  "size": "1536x1024",
  "quality": "medium",
  "n": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，保留每份原始图片或 GIF。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、质量、尺寸、格式与数量位于默认区。其余参考图、素材地址、蒙版、标注和输出细节位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
