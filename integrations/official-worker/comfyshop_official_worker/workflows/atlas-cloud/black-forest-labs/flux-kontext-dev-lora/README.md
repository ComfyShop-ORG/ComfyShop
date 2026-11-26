# FLUX.1 Kontext Dev LoRA 图像编辑

用提示词和最多三组 LoRA 权重编辑图片。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-kontext-dev-lora`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-kontext-dev-lora)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                       | 必填 | 默认值                                    | 输入约定                                                        |
| ---------------------- | ------------------------------------ | ---- | ----------------------------------------- | --------------------------------------------------------------- |
| `model`                | `execution.config.model`             | 是   | `black-forest-labs/flux-kontext-dev-lora` | 工作机从执行配置读取                                            |
| `prompt`               | `prompt`                             | 否   | —                                         | 编辑指令                                                        |
| `image`                | `source_image` 或 `source_image_url` | 否   | —                                         | 上传源图或填写公开图片 URL，任选一种                            |
| `loras`                | `loras`                              | 否   | `[]`                                      | 最多 3 项，`path` 为权重路径或 URL，`scale` 范围 0 至 4，默认 1 |
| `size`                 | `size`                               | 否   | —                                         | 像素宽*高，每边正整数且不超过 1536                              |
| `num_inference_steps`  | `num_inference_steps`                | 否   | `28`                                      | 整数 1 至 50                                                    |
| `guidance_scale`       | `guidance_scale`                     | 否   | `2.5`                                     | 0 至 20，步长 0.1                                               |
| `num_images`           | `num_images`                         | 否   | `1`                                       | 整数 1 至 4                                                     |
| `seed`                 | `seed`                               | 否   | `-1`                                      | 整数，`-1` 为随机                                               |
| `output_format`        | `output_format`                      | 否   | `jpeg`                                    | `jpeg`、`png` 或 `webp`                                         |
| `enable_base64_output` | `enable_base64_output`               | 否   | `false`                                   | 返回 Base64                                                     |
| `enable_sync_mode`     | `enable_sync_mode`                   | 否   | `false`                                   | 提交响应可直接包含成品                                          |

上传的源图由工作机转成 URL。未填写的 `size` 省略，使用接口设置。同步时工作机优先读取提交响应，必要时再轮询。示例数据中的 `enable_safety_checker` 未列入本端点的请求 Schema。

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-kontext-dev-lora.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-kontext-dev-lora.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-kontext-dev-lora.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/black-forest-labs/flux-kontext-dev-lora/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-kontext-dev-lora#usage-examples)

```json
{
  "model": "black-forest-labs/flux-kontext-dev-lora",
  "prompt": "Restore the scratches in this photograph.",
  "image": "https://example.com/photograph.jpg",
  "loras": [],
  "size": "1024*1024",
  "num_inference_steps": 28,
  "guidance_scale": 2.5,
  "num_images": 1,
  "seed": -1,
  "output_format": "jpeg",
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、源图、LoRA 权重、尺寸、图片格式和数量。高级参数为推理步数、引导强度、随机种子、素材 URL、Base64 和同步返回。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
