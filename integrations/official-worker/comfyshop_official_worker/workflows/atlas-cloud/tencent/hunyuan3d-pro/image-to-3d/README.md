# Hunyuan 3D Pro 图生 3D

根据参考图片生成带纹理的模型或纯几何白模，可设置目标面数。Atlas Cloud 模型 ID 为 `tencent/hunyuan3d-pro/image-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/tencent/hunyuan3d-pro/image-to-3d)

## 官方参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                              | 输入约定                                            |
| --------------- | ------------------------ | ---- | ----------------------------------- | --------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `tencent/hunyuan3d-pro/image-to-3d` | 工作机从执行配置读取                                |
| `image`         | `reference_image`        | 是   | 用户上传                            | PNG、JPEG 或 WebP。每边 128 至 5000 像素，最多 6 MB |
| `generate_type` | `generation_type`        | 否   | `Normal`                            | `Normal` 生成带纹理模型，`Geometry` 生成白模        |
| `enable_pbr`    | `pbr`                    | 否   | `false`                             | `Normal` 模式可生成金属度、粗糙度和法线贴图         |
| `face_count`    | `face_count`             | 否   | `500000`                            | 40000 至 1500000 的整数                             |

工作机校验参考图片后以内联 Base64 数据地址发送。直接调用 API 可提供至少 24 小时有效的公开 URL。工作机根据生成类型应用 PBR 设置。目标面数默认值来自 Atlas 的字段说明。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-hunyuan3d-pro-image-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-hunyuan3d-pro-image-to-3d.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "tencent/hunyuan3d-pro/image-to-3d",
  "image": "https://example.com/teapot.png",
  "generate_type": "Normal",
  "enable_pbr": true,
  "face_count": 500000
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 下载成品。官方样例包含 GLB、预览图和 OBJ、MTL、贴图的 ZIP 包。GLB 可在线预览，ZIP 可下载原件。[官方调用示例](https://www.atlascloud.ai/models/tencent/hunyuan3d-pro/image-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考图片和生成类型位于默认区，PBR 开关和面数在高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
