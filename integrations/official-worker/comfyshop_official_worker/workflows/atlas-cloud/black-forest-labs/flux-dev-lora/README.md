# FLUX.1 Dev LoRA 图像生成

用最多五组 LoRA 权重生成图片，也可用源图或蒙版修改局部。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-dev-lora`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-dev-lora)

## Atlas 接口参数

| Atlas 参数            | ComfyShop 字段                       | 必填 | 默认值                            | 输入约定                                                       |
| --------------------- | ------------------------------------ | ---- | --------------------------------- | -------------------------------------------------------------- |
| `model`               | `execution.config.model`             | 是   | `black-forest-labs/flux-dev-lora` | 工作机从执行配置读取                                           |
| `prompt`              | `prompt`                             | 是   | 官方可编辑示例                    | 提示词                                                         |
| `loras`               | `loras`                              | 否   | 官方示例中的 LoRA                 | 最多 5 个对象。每项 `path` 必填，`scale` 默认为 1，范围 0 至 4 |
| `size`                | `size`                               | 否   | `1024*1024`                       | 像素宽*高                                                      |
| `num_images`          | `num_images`                         | 否   | `1`                               | 整数 1 至 4                                                    |
| `image`               | `source_image` 或 `source_image_url` | 否   | 空                                | 可上传源图或填写公开图片 URL                                   |
| `mask_image`          | `mask` 或 `mask_url`                 | 否   | —                                 | 与源图一起使用。白色为重绘，黑色为保留                         |
| `strength`            | `strength`                           | 否   | `0.8`                             | 0 至 1，步长 0.01                                              |
| `num_inference_steps` | `num_inference_steps`                | 否   | `28`                              | 整数 1 至 50                                                   |
| `guidance_scale`      | `guidance_scale`                     | 否   | `2.5`                             | 0 至 20，步长 0.1                                              |
| `cfg_scale`           | `cfg_scale`                          | 否   | `1`                               | 0 至 20，步长 0.1。填写负面提示词时须大于 1                    |
| `negative_prompt`     | `negative_prompt`                    | 否   | 空                                | 指示要避开的内容                                               |
| `seed`                | `seed`                               | 否   | `-1`                              | 整数，`-1` 为随机                                              |

`loras` 填写 JSON 数组。`path` 接受 Atlas 能访问的权重路径或 URL。空白字段交由 Atlas 使用默认设置。`guidance_scale` 调节模型对正向提示词的遵循程度，`cfg_scale` 控制负面提示词。Atlas 会拒绝带有负面提示词且 CFG 不大于 1 的请求。示例数据中的 `enable_base64_output` 和 `enable_safety_checker` 未列入本接口的请求 Schema。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-dev-lora.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-dev-lora.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-dev-lora.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/black-forest-labs/flux-dev-lora/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-dev-lora#usage-examples)

```json
{
  "model": "black-forest-labs/flux-dev-lora",
  "prompt": "Super Realism, Woman in a red jacket, snowy, in the style of hyper-realistic portraiture, caninecore, mountainous vistas, timeless beauty, palewave, iconic, distinctive noses --ar 72:101 --stylize 750 --v 6",
  "loras": [
    {
      "path": "strangerzonehf/Flux-Super-Realism-LoRA",
      "scale": 1
    }
  ],
  "size": "1024*1024",
  "num_images": 1,
  "strength": 0.8,
  "num_inference_steps": 28,
  "guidance_scale": 2.5,
  "cfg_scale": 1,
  "seed": -1
}
```

从响应取 `id`（也支持 `data.id`）。工作机优先轮询本模型 Schema 中的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `output` 或 `outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、LoRA 权重、尺寸和出图数量。高级参数为源图、蒙版、重绘强度、推理步数、引导强度、CFG 强度、负面提示词、随机种子和素材 URL。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
