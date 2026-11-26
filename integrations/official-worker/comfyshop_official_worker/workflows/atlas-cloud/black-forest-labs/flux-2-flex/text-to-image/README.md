# FLUX.2 Flex 文生图

根据提示词生成 JPEG 或 PNG 图片。 Atlas Cloud 模型 ID 为 `black-forest-labs/flux-2-flex/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/black-forest-labs/flux-2-flex/text-to-image)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段            | 必填 | 默认值                                        | 输入约定                          |
| ------------------------- | ------------------------- | ---- | --------------------------------------------- | --------------------------------- |
| `model`                   | `execution.config.model`  | 是   | `black-forest-labs/flux-2-flex/text-to-image` | 工作机从执行配置读取              |
| `prompt`                  | `prompt`                  | 是   | —                                             | 描述要生成的图片                  |
| `size`                    | `size`（隐藏）            | 否   | `1024*1024`                                   | 宽*高像素，每边 256 至 2048       |
| `enable_prompt_expansion` | `enable_prompt_expansion` | 否   | `true`                                        | 生成前扩写提示词                  |
| `guidance_scale`          | `guidance_scale`          | 否   | `5`                                           | 1.5 至 10，调节对提示词的遵循程度 |
| `num_inference_steps`     | `num_inference_steps`     | 否   | `50`                                          | 整数 1 至 50                      |
| `output_format`           | `output_format`           | 否   | `jpeg`                                        | `jpeg` 或 `png`                   |
| `safety_tolerance`        | `safety_tolerance`        | 否   | `2`                                           | 整数 0 至 5，0 最严格             |
| `seed`                    | `seed`                    | 否   | `-1`                                          | 整数，`-1` 随机                   |
| `enable_base64_output`    | `enable_base64_output`    | 否   | `false`                                       | 返回 Base64                       |
| `enable_sync_mode`        | `enable_sync_mode`        | 否   | `false`                                       | 提交响应可包含成品                |

Atlas 请求使用 `size` 表示宽高。内置默认 `1024*1024`，清空此字段时由模型选择尺寸。[官方接口参数](https://www.atlascloud.ai/docs/more-models/black-forest-labs/flux-2-flex-text-to-image/generateImage)

[官方 Schema](https://static.atlascloud.ai/model/schema/black-forest-labs-flux-2-flex-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/black-forest-labs-flux-2-flex-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/black-forest-labs-flux-2-flex-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/black-forest-labs/flux-2-flex/text-to-image#usage-examples)

```json
{
  "model": "black-forest-labs/flux-2-flex/text-to-image",
  "prompt": "A huge ringed planet over a dark horizon.",
  "size": "1024*1024",
  "enable_prompt_expansion": true,
  "guidance_scale": 5,
  "num_inference_steps": 50,
  "output_format": "jpeg",
  "safety_tolerance": 2,
  "seed": -1,
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词和图片格式。高级参数为提示词扩写、引导强度、推理步数、内容审核容忍度、种子、Base64 和同步返回。尺寸在任务表单中隐藏。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
