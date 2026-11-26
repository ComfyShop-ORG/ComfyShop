# Luma Uni 1 文生图

根据提示词生成图片，可选择宽高比和 JPEG 或 PNG 格式。 Atlas Cloud 模型 ID 为 `luma/uni-1/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/luma/uni-1/text-to-image)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                     | 输入约定                                            |
| --------------- | ------------------------ | ---- | -------------------------- | --------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `luma/uni-1/text-to-image` | 工作机从执行配置读取                                |
| `prompt`        | `prompt`                 | 是   | Schema 提供可编辑示例      | 描述主体、构图、光线和风格                          |
| `aspect_ratio`  | `aspect_ratio`           | 否   | `16:9`                     | `1:1`、`3:4`、`4:3`、`9:16`、`16:9`、`9:21`、`21:9` |
| `output_format` | `output_format`          | 否   | `jpeg`                     | `jpeg` 或 `png`                                     |

指定成品格式后，工作机保存 Atlas 返回的图片原件。

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-uni-1-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-uni-1-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-uni-1-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/luma/uni-1/text-to-image#usage-examples)

```json
{
  "model": "luma/uni-1/text-to-image",
  "prompt": "晨光照在浅色大理石台面上，一杯冰咖啡旁落有柔和的窗影。",
  "aspect_ratio": "16:9",
  "output_format": "jpeg"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序下载并保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、宽高比和输出格式。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
