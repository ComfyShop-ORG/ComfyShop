# Seedream v4.5 连续生图

用一段提示词生成一组相关的 2K 或 4K 图片。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.5/sequential`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4.5/sequential)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                 |
| ---------------------- | ------------------------ | ---- | ------------------------------------ | ---------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v4.5/sequential` | 工作机从执行配置读取                     |
| `prompt`               | `prompt`                 | 是   | 无                                   | 说明整组内容和各张的区别，写明需要的张数 |
| `size`                 | `size`                   | 否   | `2048*2048`                          | 16 个 2K、4K 预设，使用 `宽*高` 像素格式 |
| `max_images`           | `max_images`             | 否   | 1                                    | 整数 1 至 15，与提示词中的张数一致       |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                                | 开启后返回 Base64 图片，由工作机解码保存 |

静态 Schema 路径列为 `generateVideo` 和 `result`。工作机依据端点文档和模型示例调用 `generateImage` 并使用 `prediction` 查询。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.5-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.5-sequential.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4.5-sequential.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4.5-sequential/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.5/sequential#usage-examples)

```json
{
  "model": "bytedance/seedream-v4.5/sequential",
  "prompt": "生成三张同一座玻璃温室的插画，依次展现清晨霜冻、午后晴朗和雨后傍晚。保持机位与几何构图一致。",
  "size": "2048*2048",
  "max_images": 3
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、尺寸和最多生成张数位于默认区。Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
