# Meshy v7 多图生 3D

用同一物体的 1 至 4 个角度生成 3D 模型，可分别提供几何与纹理参考图。Atlas Cloud 模型 ID 为 `meshy-v7/multi-image-to-3d`。[模型 API 参考](https://www.atlascloud.ai/models/meshy-v7/multi-image-to-3d)

## 官方参数

| Atlas 参数                | ComfyShop 字段                                 | 必填 | 默认值                       | 输入约定                                                    |
| ------------------------- | ---------------------------------------------- | ---- | ---------------------------- | ----------------------------------------------------------- |
| `model`                   | `execution.config.model`                       | 是   | `meshy-v7/multi-image-to-3d` | 工作机从执行配置读取                                        |
| `reference_images`        | `reference_1` 至 `reference_4`                 | 是   | 用户上传                     | 1 至 4 张几何参考图，第一张为主视图                         |
| `ultra_mode`              | `detailed_geometry`                            | 否   | `false`                      | 提升几何细节                                                |
| `should_texture`          | `textured`                                     | 否   | `true`                       | 生成纹理                                                    |
| `enable_pbr`              | `pbr`                                          | 否   | `false`                      | 生成金属度、粗糙度和法线贴图                                |
| `texture_resolution`      | `texture_resolution`                           | 否   | `2k`                         | `2k`、`4k`、`8k`                                            |
| `texture_prompt`          | `texture_prompt`                               | 否   | 用户填写                     | 最多 800 字符，优先于单图纹理                               |
| `texture_image`           | `texture_image`                                | 否   | 用户上传                     | 单张纹理参考图                                              |
| `texture_images`          | `texture_reference_1` 至 `texture_reference_4` | 否   | 用户上传                     | 1 至 4 张纹理参考图，第一张为主视图                         |
| `image_enhancement`       | `enhance_input`                                | 否   | `true`                       | 预处理几何参考图                                            |
| `remove_lighting`         | `remove_baked_lighting`                        | 否   | `true`                       | 去除基础色贴图的既有光影                                    |
| `should_remesh`           | `remesh`                                       | 否   | `false`                      | 重新拓扑以控制网格与面数                                    |
| `topology`                | `topology`                                     | 否   | `triangle`                   | `triangle` 或 `quad`                                        |
| `target_polycount`        | `face_target`                                  | 否   | `30000`                      | 100 至 300000 的整数                                        |
| `decimation_mode`         | `decimation_level`                             | 否   | 由用户选择                   | `1`、`2`、`3`、`4`，从极高到低面数。优先于指定面数          |
| `save_pre_remeshed_model` | `include_original_mesh`                        | 否   | `false`                      | 同时返回重新拓扑前的 GLB                                    |
| `pose_mode`               | `pose`                                         | 否   | 空字符串                     | 保留原姿态，或选择 `a-pose`、`t-pose`                       |
| `target_formats`          | 六个格式开关                                   | 否   | `["glb"]`                    | 从 `glb`、`obj`、`fbx`、`stl`、`usdz`、`3mf` 中选 1 至 6 种 |
| `auto_size`               | `real_world_scale`                             | 否   | `false`                      | 按估算的实物高度缩放                                        |
| `origin_at`               | `origin`                                       | 否   | `bottom`                     | `bottom` 或 `center`                                        |
| `alpha_thumbnail`         | `transparent_preview`                          | 否   | `false`                      | 额外返回透明背景预览                                        |
| `multi_view_thumbnails`   | `additional_previews`                          | 否   | `false`                      | 额外生成右侧、背面和左侧预览                                |
| `moderation`              | `moderation`                                   | 否   | `false`                      | 生成前审核源图和纹理提示词                                  |

几何图和纹理图使用 PNG 或 JPEG，各组按槽位编号提交并跳过空槽。多图纹理组请单独使用。生成纹理、重新拓扑和实物缩放开关分别控制关联参数是否发送。直接调用 API 可以提供公开 URL、Base64 数据地址或供应商素材引用。[官方 Schema](https://static.atlascloud.ai/model/schema/meshy-v7-multi-image-to-3d.json) · [官方示例数据](https://static.atlascloud.ai/model/example/meshy-v7-multi-image-to-3d.json) · [素材上传](https://www.atlascloud.ai/docs/upload-files)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。素材地址为示例。

```json
{
  "model": "meshy-v7/multi-image-to-3d",
  "reference_images": ["https://example.com/front.png", "https://example.com/side.png"],
  "should_texture": true,
  "texture_resolution": "2k",
  "target_formats": ["glb", "obj"],
  "multi_view_thumbnails": true
}
```

从提交响应的 `data.id` 取生成编号，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机下载 `data.outputs` 中的模型、贴图、材质文件和预览，并使用 `data.files` 提供的文件名。GLB 可在线预览，各格式可下载原件。将 OBJ 和它引用的 MTL、贴图保存到同一目录后在支持该格式的软件中打开。[官方调用示例](https://www.atlascloud.ai/models/meshy-v7/multi-image-to-3d#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

前两个几何参考图和纹理开关位于默认区，剩余参考图和其他设置位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
