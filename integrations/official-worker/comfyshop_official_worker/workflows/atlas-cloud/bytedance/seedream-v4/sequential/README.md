# Seedream v4 连续生图

从同一段提示词生成最多 14 张相关图片，支持自定义宽高。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4/sequential`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4/sequential)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                               |
| ---------------------- | ------------------------ | ---- | ---------------------------------- | -------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v4/sequential` | 工作机从执行配置读取                   |
| `prompt`               | `prompt`                 | 是   | 无                                 | 说明整组图像和各张的内容               |
| `size`                 | `size`                   | 否   | `2048*2048`                        | `宽*高` 像素格式，每边 1024 至 4096    |
| `max_images`           | `max_images`             | 否   | 1                                  | 整数 1 至 14，指定成品张数             |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                              | 开启后返回 Base64 图片，工作机解码保存 |

旧静态示例还有 `enable_sync_mode`。工作机依据请求 Schema 和独立端点的字段调用，使用模型 API 示例的 `prediction` 查询。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4-sequential.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4-sequential.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4-sequential/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4/sequential#usage-examples)

```json
{
  "model": "bytedance/seedream-v4/sequential",
  "prompt": "生成三张同一枝山茶花的植物插画，依次展示花蕾、初开和盛开阶段，背景保持一致。",
  "size": "2048*1536",
  "max_images": 3
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、尺寸和最多生成张数位于默认区。Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
