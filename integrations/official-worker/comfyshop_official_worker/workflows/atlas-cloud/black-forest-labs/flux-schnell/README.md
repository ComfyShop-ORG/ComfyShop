# FLUX.1 Schnell 图像生成

根据提示词生成图片，也可使用源图和蒙版修改局部。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-schnell`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-schnell)

## Atlas 接口参数

| Atlas 参数              | ComfyShop 字段                       | 必填 | 默认值                           | 输入约定                                     |
| ----------------------- | ------------------------------------ | ---- | -------------------------------- | -------------------------------------------- |
| `model`                 | `execution.config.model`             | 是   | `black-forest-labs/flux-schnell` | 工作机从执行配置读取                         |
| `prompt`                | `prompt`                             | 是   | 官方可编辑示例                   | 提示词                                       |
| `size`                  | `size`                               | 否   | `1024*1024`                      | 像素宽*高                                    |
| `num_images`            | `num_images`                         | 否   | `1`                              | 整数 1 至 4                                  |
| `image`                 | `source_image` 或 `source_image_url` | 否   | 空                               | 可上传源图或填写公开图片 URL                 |
| `mask_image`            | `mask` 或 `mask_url`                 | 否   | —                                | 蒙版。与源图一起使用，白色为重绘，黑色为保留 |
| `strength`              | `strength`                           | 否   | `0.8`                            | 0 至 1，步长 0.01                            |
| `seed`                  | `seed`                               | 否   | `-1`                             | 整数，`-1` 为随机                            |
| `enable_base64_output`  | `enable_base64_output`               | 否   | `false`                          | 以 Base64 返回成品                           |
| `enable_sync_mode`      | `enable_sync_mode`                   | 否   | `false`                          | 在提交响应中直接返回已生成的图片             |
| `enable_safety_checker` | `enable_safety_checker`（隐藏）      | 否   | `true`                           | 内置工作流保持开启                           |

提交 `size` 字符串。工作机将上传的源图与蒙版转为 URL。不给源图时可直接文生图。同步模式开启时，工作机优先使用提交响应中的成品，再按需轮询。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-schnell.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-schnell.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-schnell.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/black-forest-labs/flux-schnell/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-schnell#usage-examples)

```json
{
  "model": "black-forest-labs/flux-schnell",
  "prompt": "Cute boy with a hat, exploring nature, holding a telescope, backpack, surrounded by flowers, cartoon style, vibrant colors.",
  "size": "1024*1024",
  "num_images": 1,
  "strength": 0.8,
  "seed": -1,
  "enable_base64_output": false,
  "enable_sync_mode": false,
  "enable_safety_checker": true
}
```

从响应取 `id`（也支持 `data.id`）。工作机优先轮询本模型 Schema 中的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。支持从 `output` 或 `outputs` 保存 URL 或 Base64 图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、尺寸和出图数量。高级参数为源图、蒙版、重绘强度、随机种子、Base64、同步返回和素材 URL。安全检查在任务表单中隐藏。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
