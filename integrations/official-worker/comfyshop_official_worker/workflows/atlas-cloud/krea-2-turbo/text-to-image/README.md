# Krea 2 Turbo 文生图

根据提示词快速生成一至四张图片，支持预设和自定义尺寸。 Atlas Cloud 模型 ID 为 `krea-2-turbo/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/krea-2-turbo/text-to-image)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                 | 必填 | 默认值                       | 输入约定                                      |
| --------------- | ------------------------------ | ---- | ---------------------------- | --------------------------------------------- |
| `model`         | `execution.config.model`       | 是   | `krea-2-turbo/text-to-image` | 工作机从执行配置读取                          |
| `prompt`        | `prompt`                       | 是   | —                            | 描述要生成的图片                              |
| `image_size`    | `size_preset` 或 `custom_size` | 否   | `square_hd`                  | 六种预设，或填写 `宽x高`，最高 2048×2048 像素 |
| `num_images`    | `num_images`                   | 否   | `1`                          | 1 至 4 的整数                                 |
| `seed`          | `seed`                         | 否   | 随机                         | 指定整数可复用种子                            |
| `output_format` | `output_format`                | 否   | `png`                        | `png` 或 `jpeg`                               |

`image_size` 的预设值来自端点枚举。自定义尺寸按模型说明发送为 `WxH`，如 `1024x768`。填写自定义尺寸时覆盖预设。[Atlas Krea 模型页](https://www.atlascloud.ai/models/krea)

[官方 Schema](https://static.atlascloud.ai/model/schema/krea-2-turbo-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/krea-2-turbo-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/krea-2-turbo-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/krea-2-turbo/text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/krea-2-turbo/text-to-image#usage-examples)

```json
{
  "model": "krea-2-turbo/text-to-image",
  "prompt": "远处是雪山，近处是开满野花的草地。",
  "image_size": "1024x768",
  "num_images": 4,
  "output_format": "png"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词、尺寸预设、格式与生成数量。高级参数包括随机种子和自定义尺寸。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
