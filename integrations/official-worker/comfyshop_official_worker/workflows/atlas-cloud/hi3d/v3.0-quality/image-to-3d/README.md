# HI3D v3.0 Quality 图生 3D

从最多四张参考图还原物体的边缘、薄结构和表面细节，可生成带 PBR 材质的 3D 网格。Atlas Cloud 模型 ID 为 `hi3d/v3.0-quality/image-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/hi3d/v3.0-quality/image-to-3d)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                          | 输入约定                                                                   |
| ------------------ | ------------------------ | ---- | ------------------------------- | -------------------------------------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `hi3d/v3.0-quality/image-to-3d` | 工作机从执行配置读取                                                       |
| `image`            | `reference_image`        | 是   | 用户上传                        | JPEG、PNG 或 WebP，单张最多 20 MB                                          |
| `reference_images` | `view_1` 至 `view_3`     | 否   | 省略                            | 同一物体的 1 至 3 张补充视图，按槽位顺序发送                               |
| `multi_images_bit` | `view_slots`             | 否   | 从第一个槽位开始填充            | 前后左右各占一位，`1010` 表示上传正面与左侧。多图时 `1` 的个数与图片数相同 |
| `should_texture`   | `texture`                | 否   | `true`                          | 关闭后仅生成几何网格                                                       |
| `enable_pbr`       | `pbr`                    | 否   | `true`                          | 开启纹理时生成金属度、粗糙度和法线贴图                                     |
| `shading`          | `shading`                | 否   | `0.5`                           | 0 至 1。开启纹理时控制光照移除程度                                         |
| `rmbg`             | `remove_background`      | 否   | `true`                          | 移除背景。已经抠图时可关闭                                                 |
| `target_polycount` | `target_faces`           | 否   | 供应商选择                      | 100000 至 5000000 的整数，推荐 2000000                                     |
| `output_format`    | `output_format`          | 否   | `glb`                           | `glb`、`obj`、`stl`、`fbx`、`usdz`、`3mf`                                  |

工作机校验图片后上传至 Atlas 获得 URL。直接调用 API 可使用公开 URL 或 Base64 数据地址。单张图时供应商忽略视图位置编码。[官方 Schema](https://static.atlascloud.ai/model/schema/hi3d-v3.0-quality-image-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/hi3d-v3.0-quality-image-to-3d.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "hi3d/v3.0-quality/image-to-3d",
  "image": "https://example.com/front.png",
  "reference_images": ["https://example.com/left.png"],
  "multi_images_bit": "1010",
  "should_texture": true,
  "output_format": "glb"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。从 `data.outputs` 读取模型和渲染预览图，`data.files` 可提供文件类型和文件名。[官方调用示例](https://www.atlascloud.ai/models/hi3d/v3.0-quality/image-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考图、导出格式和纹理开关位于默认区，其余参数位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
