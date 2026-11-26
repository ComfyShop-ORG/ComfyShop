# Tripo H3.1 文生 3D

用文字描述生成 3D 网格和材质，可设置几何精度、纹理与拓扑。Atlas Cloud 模型 ID 为 `tripo-h3.1/text-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/tripo-h3.1/text-to-3d)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                  | 输入约定                               |
| ------------------ | ------------------------ | ---- | ----------------------- | -------------------------------------- |
| `model`            | `execution.config.model` | 是   | `tripo-h3.1/text-to-3d` | 工作机从执行配置读取                   |
| `prompt`           | `prompt`                 | 是   | 由用户填写              | 描述物体、形状和材质，最多 1024 个字符 |
| `negative_prompt`  | `negative_prompt`        | 否   | 由用户填写              | 描述希望避免的特征                     |
| `texture`          | `texture`                | 否   | `true`                  | 生成纹理                               |
| `pbr`              | `pbr`                    | 否   | `true`                  | 生成基于物理的渲染材质                 |
| `texture_quality`  | `texture_quality`        | 否   | `standard`              | `standard` 或 `detailed`               |
| `geometry_quality` | `geometry_quality`       | 否   | `standard`              | `standard` 或 `detailed`               |
| `face_limit`       | `face_limit`             | 否   | 由模型决定              | 目标面数为 1000 至 2000000 的整数      |
| `model_seed`       | `model_seed`             | 否   | 由模型决定              | 用于复现几何生成的整数                 |
| `image_seed`       | `image_seed`             | 否   | 由模型决定              | 用于复现文字生成概念图的整数           |
| `texture_seed`     | `texture_seed`           | 否   | 由模型决定              | 用于复现纹理生成的整数                 |
| `auto_size`        | `auto_size`              | 否   | `false`                 | 自动按以米为单位的实物尺寸缩放         |
| `quad`             | `quad`                   | 否   | `false`                 | 启用四边面网格后交付 FBX，默认交付 GLB |

省略的种子和目标面数由供应商决定。[官方 Schema](https://static.atlascloud.ai/model/schema/tripo-h3.1-text-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tripo-h3.1-text-to-3d.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "tripo-h3.1/text-to-3d",
  "prompt": "一个圆润的蓝色陶瓷花盆，釉面带细微裂纹，底部平整。",
  "negative_prompt": "花纹文字",
  "texture": true,
  "pbr": true,
  "face_limit": 50000,
  "quad": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的模型和可用的预览图。GLB 可在线预览，FBX 可下载原件。[官方调用示例](https://www.atlascloud.ai/models/tripo-h3.1/text-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、纹理和 PBR 材质位于默认区。负向提示词、质量、面数、种子、缩放和四边面开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
