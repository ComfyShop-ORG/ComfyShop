# Z-Image Turbo LoRA 文生图

根据提示词生成图片，可混合最多三个 LoRA 权重。 Atlas Cloud 模型 ID 为 `z-image/turbo-lora`。[官方模型 API](https://www.atlascloud.ai/models/z-image/turbo-lora)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值               | 输入约定                                                                                          |
| ---------------------- | ------------------------ | ---- | -------------------- | ------------------------------------------------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `z-image/turbo-lora` | 工作机从执行配置读取                                                                              |
| `prompt`               | `prompt`                 | 是   | —                    | 支持中文或英文场景描述                                                                            |
| `size`                 | `size`                   | 否   | `1024*1024`          | `宽*高`，每边最多 1,536 像素                                                                      |
| `loras`                | `loras`                  | 否   | `[]`                 | 最多 3 项的对象数组。`path` 必填，接受权重 ID 或 `.safetensors` URL。`scale` 可选，0 至 4，默认 1 |
| `seed`                 | `seed`                   | 否   | `-1`                 | `-1` 为随机，指定整数可复用种子                                                                   |
| `num_inference_steps`  | `num_inference_steps`    | 否   | `9`                  | 大于等于 1 的整数                                                                                 |
| `guidance_scale`       | `guidance_scale`         | 否   | `1`                  | 提示词引导强度                                                                                    |
| `output_format`        | `output_format`          | 否   | `png`                | `png`、`jpeg`、`webp`                                                                             |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | `false`              | 等待上传完成并在提交响应中返回成品                                                                |
| `enable_base64_output` | `enable_base64_output`   | 否   | `false`              | 返回 Base64 图像                                                                                  |

工作机将 `loras` 的 JSON 文本解析为对象数组，保留填写顺序。可清空该字段以交给接口使用默认空数组。

[官方 Schema](https://static.atlascloud.ai/model/schema/z-image-turbo-lora.json) · [官方示例数据](https://static.atlascloud.ai/model/example/z-image-turbo-lora.json) · [模型说明](https://static.atlascloud.ai/model/readme/z-image-turbo-lora.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/z-image/turbo-lora/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/z-image/turbo-lora#usage-examples)

```json
{
  "model": "z-image/turbo-lora",
  "prompt": "复古印刷风格的山脉海报。",
  "loras": [
    {
      "path": "example-owner/example-lora",
      "scale": 0.7
    }
  ],
  "size": "1024*1024",
  "seed": -1,
  "num_inference_steps": 9,
  "guidance_scale": 1,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词和输出尺寸。高级参数包括 LoRA、种子、推理步数、提示词引导强度、格式、同步返回和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
