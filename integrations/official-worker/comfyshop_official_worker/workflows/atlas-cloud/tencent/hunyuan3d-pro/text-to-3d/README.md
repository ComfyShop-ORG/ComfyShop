# Hunyuan 3D Pro 文生 3D

根据提示词生成带纹理的模型或纯几何白模，可设置目标面数。Atlas Cloud 模型 ID 为 `tencent/hunyuan3d-pro/text-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/tencent/hunyuan3d-pro/text-to-3d)

## 官方参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                                     |
| --------------- | ------------------------ | ---- | ---------------------------------- | -------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `tencent/hunyuan3d-pro/text-to-3d` | 工作机从执行配置读取                         |
| `prompt`        | `prompt`                 | 是   | 由用户填写                         | 描述物体外观，最多 1024 个字符               |
| `generate_type` | `generation_type`        | 否   | `Normal`                           | `Normal` 生成带纹理模型，`Geometry` 生成白模 |
| `enable_pbr`    | `pbr`                    | 否   | `false`                            | `Normal` 模式可生成金属度、粗糙度和法线贴图  |
| `face_count`    | `face_count`             | 否   | `500000`                           | 40000 至 1500000 的整数                      |

工作机根据生成类型应用 PBR 设置。目标面数默认值来自 Atlas 的字段说明。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-hunyuan3d-pro-text-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-hunyuan3d-pro-text-to-3d.json)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "tencent/hunyuan3d-pro/text-to-3d",
  "prompt": "有釉面的蓝色陶瓷茶壶，圆形提梁，壶身有浅浮雕。",
  "generate_type": "Normal",
  "enable_pbr": true,
  "face_count": 500000
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 下载成品。官方样例包含 GLB、预览图和 OBJ、MTL、贴图的 ZIP 包。GLB 可在线预览，ZIP 可下载原件。[官方调用示例](https://www.atlascloud.ai/models/tencent/hunyuan3d-pro/text-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词和生成类型位于默认区，PBR 开关和面数在高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
