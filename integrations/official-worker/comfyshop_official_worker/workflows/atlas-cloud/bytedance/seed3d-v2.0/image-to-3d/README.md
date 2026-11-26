# Seed3D 2.0 图生 3D

根据一张参考图生成带 PBR 材质的 3D 网格。Atlas Cloud 模型 ID 为 `bytedance/seed3d-v2.0/image-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seed3d-v2.0/image-to-3d)

## 官方参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                              | 输入约定                                                                                 |
| ---------------------- | ------------------------ | ---- | ----------------------------------- | ---------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seed3d-v2.0/image-to-3d` | 工作机从执行配置读取                                                                     |
| `image`                | `reference_image`        | 是   | 用户上传                            | JPEG、PNG、WebP 或 BMP。最多 10 MB，总像素小于 4096 × 4096，宽高比严格在 0.4 至 2.5 之间 |
| `subdivision_level`    | `subdivision_level`      | 否   | `medium`                            | `high` 约 100 万面，`medium` 约 50 万面，`low` 约 10 万面                                |
| `file_format`          | `file_format`            | 否   | `glb`                               | `glb`、`obj`、`usd`、`usdz`                                                              |
| `enable_base64_output` | `base64_output`          | 否   | `false`                             | 开启后从响应解码 ZIP                                                                     |

工作机校验参考图片后以内联 Base64 数据地址发送。直接调用也可使用公开 URL。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seed3d-v2.0-image-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seed3d-v2.0-image-to-3d.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "bytedance/seed3d-v2.0/image-to-3d",
  "image": "https://example.com/sculpture.png",
  "subdivision_level": "medium",
  "file_format": "glb",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `data.outputs` 获取 ZIP 链接，链接有效期为 24 小时。开启 Base64 时，工作机解码并回传 ZIP 原件。官方示例还附带可在线预览的 GLB。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seed3d-v2.0/image-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考图片和文件格式位于默认区，细分等级和 Base64 开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
