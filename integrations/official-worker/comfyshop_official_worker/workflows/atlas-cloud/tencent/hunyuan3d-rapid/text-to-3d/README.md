# Hunyuan 3D Rapid 文生 3D

根据提示词生成 3D 模型，可选择输出格式和材质。Atlas Cloud 模型 ID 为 `tencent/hunyuan3d-rapid/text-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/tencent/hunyuan3d-rapid/text-to-3d)

## 官方参数

| Atlas 参数        | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                  |
| ----------------- | ------------------------ | ---- | ------------------------------------ | ----------------------------------------- |
| `model`           | `execution.config.model` | 是   | `tencent/hunyuan3d-rapid/text-to-3d` | 工作机从执行配置读取                      |
| `prompt`          | `prompt`                 | 是   | 由用户填写                           | 描述形状、材质和颜色，最多 1024 个字符    |
| `format`          | `output_format`          | 否   | `GLB`                                | `GLB`、`OBJ`、`USDZ`、`FBX`、`STL`、`MP4` |
| `enable_pbr`      | `pbr`                    | 否   | `false`                              | 生成金属度、粗糙度和法线贴图              |
| `enable_geometry` | `include_geometry`       | 否   | `false`                              | 同时输出一份无纹理的 GLB 网格             |

GLB 可在线预览，MP4 可在结果中播放。工作机保存供应商返回的模型、预览及配套文件，各格式可下载原件。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-hunyuan3d-rapid-text-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-hunyuan3d-rapid-text-to-3d.json)

## API 调用

将 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "tencent/hunyuan3d-rapid/text-to-3d",
  "prompt": "浅绿色玻璃花瓶，圆柱底座，瓶肩渐收，表面有纵向纹理。",
  "format": "GLB",
  "enable_pbr": true,
  "enable_geometry": false
}
```

从响应读取 `data.id` 后轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，完成时从 `data.outputs` 获取成品地址。[官方调用示例](https://www.atlascloud.ai/models/tencent/hunyuan3d-rapid/text-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词和输出格式位于默认区，PBR 与几何输出开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
