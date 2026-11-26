# Hunyuan 3D Rapid 图生 3D

根据一张参考图片生成 3D 模型，可选择文件格式、材质和纯几何输出。Atlas Cloud 模型 ID 为 `tencent/hunyuan3d-rapid/image-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/tencent/hunyuan3d-rapid/image-to-3d)

## 官方参数

| Atlas 参数        | ComfyShop 字段           | 必填 | 默认值                                | 输入约定                                              |
| ----------------- | ------------------------ | ---- | ------------------------------------- | ----------------------------------------------------- |
| `model`           | `execution.config.model` | 是   | `tencent/hunyuan3d-rapid/image-to-3d` | 工作机从执行配置读取                                  |
| `image`           | `reference_image`        | 是   | 用户上传                              | PNG、JPEG 或 WebP。每边 128 至 5000 像素，最多 4.5 MB |
| `format`          | `output_format`          | 否   | `GLB`                                 | `GLB`、`OBJ`、`USDZ`、`FBX`、`STL`、`MP4`             |
| `enable_pbr`      | `pbr`                    | 否   | `false`                               | 生成金属度、粗糙度和法线贴图                          |
| `enable_geometry` | `include_geometry`       | 否   | `false`                               | 同时输出无纹理的 GLB 网格                             |

工作机从平台读取图片原件，校验格式、边长和文件大小，再以内联 Base64 数据地址提交。直接调用 API 也可提供至少 24 小时有效的公开 URL。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-hunyuan3d-rapid-image-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-hunyuan3d-rapid-image-to-3d.json)

## API 调用

将 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。示例中的图片地址请换成可公开访问的素材地址。

```json
{
  "model": "tencent/hunyuan3d-rapid/image-to-3d",
  "image": "https://example.com/object.png",
  "format": "GLB",
  "enable_pbr": true,
  "enable_geometry": true
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 获取模型、可用的预览和配套文件。GLB 可在线预览，MP4 可播放。[官方调用示例](https://www.atlascloud.ai/models/tencent/hunyuan3d-rapid/image-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考图和输出格式位于默认区，PBR 与纯几何输出开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
