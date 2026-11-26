# GPT Image 2.5 Flare 图像编辑

按提示词编辑多张参考图，可用蒙版指定首图的修改范围。 Atlas Cloud 模型 ID 为 `openai/gpt-image-2.5-flare/edit`。[官方模型 API](https://www.atlascloud.ai/models/openai/gpt-image-2.5-flare/edit)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                                       | 必填 | 默认值                            | 输入约定                                                                                             |
| --------------- | ---------------------------------------------------- | ---- | --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `model`         | `execution.config.model`                             | 是   | `openai/gpt-image-2.5-flare/edit` | 工作机从执行配置读取                                                                                 |
| `prompt`        | `prompt`                                             | 是   | 官方英文草地示例                  | 最长 32000 字符                                                                                      |
| `images`        | `reference_1` 至 `reference_16`、`reference_sources` | 是   | 无                                | 1 至 16 个公开 URL、Base64 data URL 或 Atlas `asset://ID` 引用                                       |
| `mask`          | `mask` 或 `mask_source`                              | 否   | 无                                | 与首图同尺寸的透明 PNG，透明像素标记编辑区域。可用上传、公开 URL、Base64 或 Atlas 素材引用           |
| `quality`       | `quality`                                            | 否   | `medium`                          | `auto`、`low`、`medium`、`high`、`xhigh`、`max`                                                      |
| `size`          | `size`、`custom_size`                                | 否   | `1024x1024`                       | `auto`、预设或自定义 `宽x高`。每边 256 至 3840 且为 16 的倍数，总像素最多 8294400，宽高比 1:3 至 3:1 |
| `background`    | `background`                                         | 否   | `auto`                            | `auto`、`opaque`、`transparent`。透明要求 PNG 或 WebP                                                |
| `output_format` | `output_format`                                      | 否   | `png`                             | `png`、`jpeg` 或 `webp`                                                                              |
| `moderation`    | `moderation`                                         | 否   | `auto`                            | `auto` 或 `low`                                                                                      |
| `n`             | `n`                                                  | 否   | 1                                 | 整数 1 至 10                                                                                         |

尺寸预设列未单独列出 `1024x1024`，选接口默认值时由 Atlas 使用这一尺寸。工作机按编号发送上传图片，再按行发送文本来源。文本来源字段上限为 4 MiB。上传蒙版使用小于 4 MB 的 PNG，Atlas 负责校验其尺寸与目标区域。Atlas 的产品概览提到 2.5 系列兼容标注，本接口的 Schema 和专用调用示例仅确认蒙版。[Atlas 系列概览](https://www.atlascloud.ai/models/gpt-image-2.6) · [OpenAI 蒙版接口格式](https://developers.openai.com/api/reference/python/resources/images/methods/edit) · [官方 Schema](https://static.atlascloud.ai/model/schema/openai-gpt-image-2.5-flare-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/openai-gpt-image-2.5-flare-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/openai-gpt-image-2.5-flare-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址替换为实际素材。[官方调用示例](https://www.atlascloud.ai/models/openai/gpt-image-2.5-flare/edit#usage-examples)

```json
{
  "model": "openai/gpt-image-2.5-flare/edit",
  "prompt": "把窗外换成柔和晨光下的草地，保持室内陈设和窗框。",
  "images": ["https://example.com/window.jpg"],
  "mask": "https://example.com/window-mask.png",
  "quality": "low",
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，下载原件。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、质量、尺寸、格式与数量位于默认区。其余图片、素材地址、蒙版及输出细节位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
