# Seedream v5.0 Pro 图层拆分

将一张原图拆成底图和最多 16 张透明 PNG 图层，保存图层位置、名称、说明和叠放顺序。Atlas Cloud 模型 ID 为 `bytedance/seedream-v5.0-pro/layer-decomposition`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/layer-decomposition)

## Atlas 接口参数

| Atlas 参数                     | ComfyShop 字段            | 必填     | 默认值                                            | 输入约定                                                                             |
| ------------------------------ | ------------------------- | -------- | ------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `model`                        | `execution.config.model`  | 请求固定 | `bytedance/seedream-v5.0-pro/layer-decomposition` | 工作机始终发送模型 ID                                                                |
| `image`                        | `image` 或 `image_source` | 是       | 无                                                | 单张图片 URL 或 Base64 data URL。支持 PNG、JPEG、WebP、BMP、TIFF 和 GIF              |
| `prompt`                       | `prompt`                  | 否       | 自动拆分                                          | 指明要拆分的元素，支持 `<bbox>x1 y1 x2 y2</bbox>`，坐标从左上角起按 0 至 1000 归一化 |
| `size`                         | `size`                    | 否       | `auto`                                            | `auto`、`1K`、`1.5K`、`2K`                                                           |
| `output_format`                | `output_format`           | 否       | `jpeg`                                            | 底图为 `jpeg` 或 `png`，拆出的图层为透明 PNG                                         |
| `optimize_prompt_options.mode` | `optimization`            | 否       | `standard`                                        | `standard` 或 `fast`，工作机发送为 `optimize_prompt_options` 对象                    |
| `enable_sync_mode`             | `enable_sync_mode`        | 否       | false                                             | 等到生成完成后从提交响应取结果                                                       |
| `enable_base64_output`         | `enable_base64_output`    | 否       | false                                             | 返回 Base64 图片，工作机解码保存                                                     |

总像素限 262144 至 36000000，宽高比限 1:16 至 16:1，文件最大 30 MB。上传槽位和素材地址二选一。TIFF 可通过地址或 Base64 data URL 提供，内联文本上限 4 MiB。直接上传的原件在提交前校验格式、大小和尺寸，远程素材由 Atlas 校验。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v5.0-pro-layer-decomposition.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v5.0-pro-layer-decomposition.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v5.0-pro-layer-decomposition.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seedream-v5.0-pro/layer-decomposition",
  "image": "https://example.com/poster.png",
  "prompt": "拆出主标题 <bbox>120 80 880 250</bbox>。",
  "size": "1K",
  "output_format": "png",
  "optimize_prompt_options": { "mode": "standard" },
  "enable_sync_mode": false
}
```

使用预测编号轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `outputs` 顺序保存底图和图层，并将 `layers` 保存为 JSON。第一个图像是底图，`z_index` 为 0。后续图层的 `bounding_box.absolute` 为像素坐标，`bounding_box.normalized` 为 0 至 1000 的归一化坐标。图层名称与描述也保存在 JSON 中。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v5.0-pro/layer-decomposition#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图、拆分说明和尺寸位于默认区。素材地址、底图格式、优化和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
