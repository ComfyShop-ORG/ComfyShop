# Seedream v4 文生图

根据提示词生成图片，接受自定义宽高。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                  | 输入约定                               |
| ---------------------- | ------------------------ | ---- | ----------------------- | -------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v4` | 工作机从执行配置读取                   |
| `prompt`               | `prompt`                 | 是   | 无                      | 描述要生成的画面                       |
| `size`                 | `size`                   | 否   | `2048*2048`             | `宽*高` 像素格式，每边 1024 至 4096    |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                   | 开启后返回 Base64 图片，工作机解码保存 |

旧静态示例含 `enable_sync_mode`。该模型的请求 Schema、端点文档和模型 API 参数表都只列出上表参数。模型 API 的轮询示例使用 `prediction`。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4#usage-examples)

```json
{
  "model": "bytedance/seedream-v4",
  "prompt": "生成一张松林清晨摄影图，低角度的雾与阳光穿过树干，保留自然色彩。",
  "size": "3072*2816",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
