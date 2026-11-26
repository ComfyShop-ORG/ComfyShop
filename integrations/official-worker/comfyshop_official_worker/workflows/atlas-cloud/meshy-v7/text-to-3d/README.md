# Meshy v7 文生 3D

根据文字生成 3D 模型，可一次生成带纹理的成品，也可生成未贴图的网格预览。Atlas Cloud 模型 ID 为 `meshy-v7/text-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/meshy-v7/text-to-3d)

## 官方参数

| Atlas 参数           | ComfyShop 字段           | 必填 | 默认值                | 输入约定                                                    |
| -------------------- | ------------------------ | ---- | --------------------- | ----------------------------------------------------------- |
| `model`              | `execution.config.model` | 是   | `meshy-v7/text-to-3d` | 工作机从执行配置读取                                        |
| `prompt`             | `prompt`                 | 是   | 由用户填写            | 描述物体形状和外观，最多 800 个字符                         |
| `mode`               | `generation_mode`        | 否   | `full`                | `full` 生成网格与纹理，`preview` 生成未贴图的网格           |
| `ultra_mode`         | `detailed_geometry`      | 否   | `false`               | 提升几何细节                                                |
| `enable_pbr`         | `pbr`                    | 否   | `false`               | 生成金属度、粗糙度和法线贴图                                |
| `texture_resolution` | `texture_resolution`     | 否   | `2k`                  | `2k`、`4k`、`8k`                                            |
| `texture_prompt`     | `texture_prompt`         | 否   | 用户填写              | 最多 800 字符，优先于单图纹理                               |
| `texture_image`      | `texture_image`          | 否   | 用户上传              | 单张纹理参考图                                              |
| `should_remesh`      | `remesh`                 | 否   | `false`               | 重新拓扑以控制网格与面数                                    |
| `topology`           | `topology`               | 否   | `triangle`            | `triangle` 或 `quad`                                        |
| `target_polycount`   | `face_target`            | 否   | `30000`               | 100 至 300000 的整数                                        |
| `decimation_mode`    | `decimation_level`       | 否   | 由用户选择            | `1`、`2`、`3`、`4`，从极高到低面数。优先于指定面数          |
| `pose_mode`          | `pose`                   | 否   | 空字符串              | 保留原姿态，或选择 `a-pose`、`t-pose`                       |
| `target_formats`     | 六个格式开关             | 否   | `["glb"]`             | 从 `glb`、`obj`、`fbx`、`stl`、`usdz`、`3mf` 中选 1 至 6 种 |
| `auto_size`          | `real_world_scale`       | 否   | `false`               | 按估算的实物高度缩放                                        |
| `origin_at`          | `origin`                 | 否   | `bottom`              | `bottom` 或 `center`                                        |
| `alpha_thumbnail`    | `transparent_preview`    | 否   | `false`               | 额外返回透明背景预览                                        |
| `moderation`         | `moderation`             | 否   | `false`               | 生成前审核文字和已提供的纹理图                              |

`full` 模式可同时生成网格和纹理。纹理图使用 PNG 或 JPEG，纹理提示词优先于纹理图。`preview` 模式生成网格，工作机省略纹理参数。重新拓扑和实物缩放开关控制各自的关联参数。直接调用 API 时可用公开 URL、Base64 或供应商素材引用指定纹理图。[官方 Schema](https://static.atlascloud.ai/model/schema/meshy-v7-text-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/meshy-v7-text-to-3d.json) · [素材上传](https://www.atlascloud.ai/docs/upload-files)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "meshy-v7/text-to-3d",
  "prompt": "一把弧形靠背的浅色木椅，结构简洁，木纹自然。",
  "mode": "full",
  "texture_resolution": "2k",
  "target_formats": ["glb", "obj"],
  "alpha_thumbnail": true
}
```

从提交响应的 `data.id` 取生成编号，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机下载 `data.outputs` 中的模型、贴图、材质文件和预览，并使用 `data.files` 提供的文件名。GLB 可在线预览，各格式可下载原件。将 OBJ 和它引用的 MTL、贴图保存到同一目录后在支持该格式的软件中打开。[官方调用示例](https://www.atlascloud.ai/models/meshy-v7/text-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词和生成模式位于默认区，网格、纹理和导出参数位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
