# FLUX.1 Kontext Dev 图像编辑

根据提示词修改源图，可控制推理参数和出图数量。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-kontext-dev`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-kontext-dev)

## Atlas 接口参数

| Atlas 参数              | ComfyShop 字段                       | 必填 | 默认值                               | 输入约定                             |
| ----------------------- | ------------------------------------ | ---- | ------------------------------------ | ------------------------------------ |
| `model`                 | `execution.config.model`             | 是   | `black-forest-labs/flux-kontext-dev` | 工作机从执行配置读取                 |
| `prompt`                | `prompt`                             | 是   | 官方可编辑示例                       | 提示词                               |
| `size`                  | `size`（隐藏）                       | 否   | —                                    | 像素宽*高。工作流值为空时省略        |
| `num_images`            | `num_images`                         | 否   | `1`                                  | 整数 1 至 4                          |
| `image`                 | `source_image` 或 `source_image_url` | 否   | 官方示例图                           | 上传源图或填写公开图片 URL，任选一种 |
| `num_inference_steps`   | `num_inference_steps`                | 否   | `28`                                 | 整数 1 至 50                         |
| `guidance_scale`        | `guidance_scale`                     | 否   | `2.5`                                | 1 至 20，步长 0.1                    |
| `seed`                  | `seed`                               | 否   | `-1`                                 | 整数，`-1` 为随机                    |
| `enable_base64_output`  | `enable_base64_output`               | 否   | `false`                              | 以 Base64 返回成品                   |
| `enable_safety_checker` | `enable_safety_checker`（隐藏）      | 否   | `true`                               | 内置工作流保持开启                   |

工作机将上传的源图转换为 URL。未选源图也未填 URL 时省略 `image`，接口 Schema 为它提供官方示例图默认值。[官方示例图](https://static.atlascloud.ai/media/images/1750940187685254815_W4yPaBQU.jpg)

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-kontext-dev.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-kontext-dev.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-kontext-dev.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/black-forest-labs/flux-kontext-dev/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-kontext-dev#usage-examples)

```json
{
  "model": "black-forest-labs/flux-kontext-dev",
  "prompt": "Change the car color to red.",
  "image": "https://static.atlascloud.ai/media/images/1750940187685254815_W4yPaBQU.jpg",
  "num_images": 1,
  "num_inference_steps": 28,
  "guidance_scale": 2.5,
  "seed": -1,
  "enable_base64_output": false,
  "enable_safety_checker": true
}
```

从响应取 `id`（也支持 `data.id`）。工作机优先轮询本模型 Schema 中的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。支持从 `output` 或 `outputs` 保存 URL 或 Base64 图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、出图数量和源图。高级参数为推理步数、引导强度、随机种子、Base64 和源图 URL。尺寸和安全检查在任务表单中隐藏。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
