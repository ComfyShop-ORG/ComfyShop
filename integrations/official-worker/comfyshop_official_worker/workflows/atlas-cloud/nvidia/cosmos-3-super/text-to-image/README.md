# NVIDIA Cosmos 3 Super 文生图

根据提示词生成图片，可选预设尺寸或自定义宽高。 Atlas Cloud 模型 ID 为 `nvidia/cosmos-3-super/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/nvidia/cosmos-3-super/text-to-image)

## Atlas 接口参数

| Atlas 参数              | ComfyShop 字段                                    | 必填 | 默认值                                | 输入约定                                                                                                                                                        |
| ----------------------- | ------------------------------------------------- | ---- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                 | `execution.config.model`                          | 是   | `nvidia/cosmos-3-super/text-to-image` | 工作机从执行配置读取                                                                                                                                            |
| `prompt`                | `prompt`                                          | 是   | —                                     | 最多 2,500 字符                                                                                                                                                 |
| `image_size`            | `size_preset`，或 `output_width`、`output_height` | 否   | `landscape_16_9`                      | 预设 `square_hd`、`square`、`portrait_4_3`、`portrait_16_9`、`landscape_4_3`、`landscape_16_9`。自定义对象 `width`、`height` 各 1 至 14,142，未填写的边默认 512 |
| `output_format`         | `output_format`                                   | 否   | `jpeg`                                | `jpeg` 或 `png`                                                                                                                                                 |
| `negative_prompt`       | `negative_prompt`                                 | 否   | 空字符串                              | 描述要排除的内容                                                                                                                                                |
| `num_inference_steps`   | `num_inference_steps`                             | 否   | `28`                                  | 1 至 50 的整数                                                                                                                                                  |
| `guidance_scale`        | `guidance_scale`                                  | 否   | `4`                                   | 1 至 20 的数值                                                                                                                                                  |
| `seed`                  | `seed`                                            | 否   | 随机                                  | 非负整数                                                                                                                                                        |
| `enable_safety_checker` | `enable_safety_checker`                           | 否   | `false`                               | 启用内容检查                                                                                                                                                    |

自定义宽高都留空时，`image_size` 发送预设字符串。填写任一边时，工作机发送包含已填写边的对象，其余边沿用接口默认值。推理步数按请求 Schema 上限 50 校验，模型说明页列出了 100。

[官方 Schema](https://static.atlascloud.ai/model/schema/nvidia-cosmos-3-super-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/nvidia-cosmos-3-super-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/nvidia-cosmos-3-super-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/nvidia/cosmos-3-super-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/nvidia/cosmos-3-super/text-to-image#usage-examples)

```json
{
  "model": "nvidia/cosmos-3-super/text-to-image",
  "prompt": "黄昏街边的花店，室内的灯透过玻璃窗。",
  "image_size": "landscape_16_9",
  "num_inference_steps": 28,
  "guidance_scale": 4,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词、尺寸预设和输出格式。高级参数包括自定义宽高、反向提示词、推理步数、引导强度、种子及内容检查。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
