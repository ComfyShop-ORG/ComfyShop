# Wan 2.7 文生图

从提示词生成图片，可选尺寸、张数与调色板。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                          | 输入约定                                                                          |
| ---------------------- | ------------------------ | ---- | ------------------------------- | --------------------------------------------------------------------------------- |
| `model`                | `execution.config.model` | 是   | `alibaba/wan-2.7/text-to-image` | 工作机从执行配置读取                                                              |
| `prompt`               | `prompt`                 | 是   | 无                              | 最多 5,000 字符                                                                   |
| `size`                 | `size` 或 `custom_size`  | 否   | `2K`                            | `1K`、`2K` 或 `宽*高`。自定义总像素 589,824 至 4,194,304，长短边比例最多 8:1      |
| `n`                    | `n`                      | 否   | 1                               | 1 至 4 张                                                                         |
| `color_palette`        | `color_palette`          | 否   | 无                              | 3 至 10 个 `{hex,ratio}` 对象。六位十六进制色码，百分比保留两位小数，合计 100.00% |
| `thinking_mode`        | `thinking_mode`          | 否   | true                            | 启用思考模式                                                                      |
| `seed`                 | `seed`                   | 否   | -1                              | 整数范围 -1 至 2147483647。-1 使用随机种子                                        |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | false                           | 等待生成完成                                                                      |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                           | 返回 Base64 图片                                                                  |

自定义尺寸覆盖下拉选项。Atlas 模型说明补充了自定义尺寸写法。宽高与调色板总和的限制依据模型厂商文档。[阿里云模型参数](https://www.alibabacloud.com/help/en/model-studio/wan-image-generation-and-editing-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/text-to-image#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/text-to-image",
  "prompt": "画一张海湾雨后风景，岸边岩石和浪花形成前景，采用低饱和色调。",
  "size": "2048*2048",
  "n": 1,
  "color_palette": [
    {
      "hex": "#274A67",
      "ratio": "50.00%"
    },
    {
      "hex": "#819A9F",
      "ratio": "35.00%"
    },
    {
      "hex": "#EBDBC3",
      "ratio": "15.00%"
    }
  ],
  "thinking_mode": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、预设尺寸与张数位于默认区。自定义尺寸、调色板、思考模式、种子和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
