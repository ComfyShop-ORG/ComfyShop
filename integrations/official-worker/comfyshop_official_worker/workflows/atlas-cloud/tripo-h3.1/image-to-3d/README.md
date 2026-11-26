# Tripo H3.1 图生 3D

Atlas Cloud 模型 ID 为 `tripo-h3.1/image-to-3d`。上传参考图后生成 3D 网格。默认交付可预览的 GLB，开启四边面时交付可下载的 FBX。[官方 API 与输入 Schema](https://www.atlascloud.ai/models/tripo-h3.1/image-to-3d)

## 参数

| ComfyShop 字段      | Atlas 参数          | 必填 | 初始值           | 说明                                     |
| ------------------- | ------------------- | ---- | ---------------- | ---------------------------------------- |
| 工作机配置          | `model`             | 是   | 模型 ID          | 从 `execution.config.model` 读取         |
| `reference_image`   | `image_url`         | 是   | 用户上传         | 将参考图片上传后作为 URL 提交            |
| `texture`           | `texture`           | 否   | `true`           | 生成纹理                                 |
| `pbr`               | `pbr`               | 否   | `true`           | 生成 PBR 材质                            |
| `texture_quality`   | `texture_quality`   | 否   | `standard`       | `standard` 或 `detailed`                 |
| `geometry_quality`  | `geometry_quality`  | 否   | `standard`       | `standard` 或 `detailed`                 |
| `texture_alignment` | `texture_alignment` | 否   | `original_image` | `original_image` 或 `geometry`           |
| `orientation`       | `orientation`       | 否   | `default`        | `default` 或 `align_image`               |
| `face_limit`        | `face_limit`        | 否   | 空               | 1000 至 2000000 的整数，省略时由模型决定 |
| `model_seed`        | `model_seed`        | 否   | 空               | 几何种子                                 |
| `texture_seed`      | `texture_seed`      | 否   | 空               | 纹理种子                                 |
| `auto_size`         | `auto_size`         | 否   | `false`          | 按实物尺寸缩放，单位为米                 |
| `quad`              | `quad`              | 否   | `false`          | 生成四边面并交付 FBX                     |

## 调用及成品

工作机使用 `uploadMedia` 上传参考图，再凭 `Authorization: Bearer <API_KEY>` 向 `POST https://api.atlascloud.ai/api/v1/model/generateImage` 发送请求。[官方素材上传](https://www.atlascloud.ai/docs/upload-files)

```json
{
  "model": "tripo-h3.1/image-to-3d",
  "image_url": "https://example.com/ceramic-vase.png",
  "texture": true,
  "pbr": true,
  "quad": false
}
```

从提交结果读取 `data.id`，用 `GET /api/v1/model/prediction/{id}` 续查并下载完成响应的 `data.outputs`。平台接收 3D 原件和随任务返回的预览图。GLB 进入现有交互预览，FBX 可下载原件。[官方预测文档](https://www.atlascloud.ai/docs/predictions)

## 参数布局与译文

参考图、纹理和 PBR 在默认区，精度、对齐、种子和拓扑选项在高级区。工作流标识为 `tripo-h31-image-to-3d`。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../docs/deployment.md#官方工作机)
