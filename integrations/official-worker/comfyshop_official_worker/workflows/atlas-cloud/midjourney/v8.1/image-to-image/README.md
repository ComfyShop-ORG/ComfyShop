# Midjourney V8.1 图生图

根据一张输入图片和提示词生成 4 张改编图片，可另外提供风格参考。 Atlas Cloud 模型 ID 为 `midjourney/v8.1/image-to-image`。[官方模型 API](https://www.atlascloud.ai/models/midjourney/v8.1/image-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                | 必填 | 默认值                           | 输入约定                                                          |
| ---------------------- | --------------------------------------------- | ---- | -------------------------------- | ----------------------------------------------------------------- |
| `model`                | `execution.config.model`                      | 是   | `midjourney/v8.1/image-to-image` | 工作机从执行配置读取                                              |
| `image`                | `input_image` 或 `input_image_source`         | 是   | —                                | 上传输入图或提供公开 HTTPS 图片地址                               |
| `prompt`               | `prompt`                                      | 是   | —                                | 改编描述最多 1,024 字符                                           |
| `sref`                 | `style_reference` 或 `style_reference_source` | 否   | —                                | 上传风格图或提供公开 HTTPS 图片地址                               |
| `aspect_ratio`         | `aspect_ratio`                                | 否   | `1:1`                            | `1:1`、`9:16`、`16:9`、`4:3`、`3:4`、`2:3`、`3:2`、`9:21`、`21:9` |
| `hd`                   | `hd`                                          | 否   | `false`                          | 原生 2K，Atlas 按标准档位的 1.5 倍计费                            |
| `stylize`              | `stylize`                                     | 否   | `0`                              | 整数 0–1,000                                                      |
| `chaos`                | `chaos`                                       | 否   | `0`                              | 整数 0–100                                                        |
| `weird`                | `weird`                                       | 否   | `0`                              | 整数 0–3,000                                                      |
| `quality`              | `quality`                                     | 否   | `1`                              | 数值 `1` 或 `4`。`4` 增加细节，生成耗时更长                       |
| `seed`                 | `seed`                                        | 否   | `-1`                             | 整数，`-1` 为随机                                                 |
| `enable_base64_output` | `enable_base64_output`                        | 否   | `false`                          | Base64 图片由工作机解码后保存                                     |

输入图决定要改编的内容，`sref` 提供独立的风格参考。Atlas 每次任务返回四张图片。

[官方 Schema](https://static.atlascloud.ai/model/schema/midjourney-v8.1-image-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/midjourney-v8.1-image-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/midjourney-v8.1-image-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/midjourney/v8.1/image-to-image#usage-examples)

```json
{
  "model": "midjourney/v8.1/image-to-image",
  "image": "https://example.com/landscape.png",
  "prompt": "把图中的山间湖泊画成细致的水彩画。",
  "sref": "https://example.com/style.png",
  "aspect_ratio": "1:1",
  "hd": false,
  "stylize": 0,
  "chaos": 0,
  "weird": 0,
  "quality": 1,
  "seed": -1,
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为输入图、提示词、风格参考图、宽高比和原生 2K。高级参数为输入图片 URL、风格参考图 URL、风格化强度、变化幅度、奇异度、细节质量、随机种子和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
