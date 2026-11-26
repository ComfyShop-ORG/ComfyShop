# Seedream v4.5 文生图

根据提示词生成图片，提供 2K 与 4K 尺寸预设。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.5`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4.5)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                    | 输入约定                                 |
| ---------------------- | ------------------------ | ---- | ------------------------- | ---------------------------------------- |
| `model`                | `execution.config.model` | 是   | `bytedance/seedream-v4.5` | 工作机从执行配置读取                     |
| `prompt`               | `prompt`                 | 是   | 无                        | 描述要生成的主体、构图与文字             |
| `size`                 | `size`                   | 否   | `2048*2048`               | 16 个 2K、4K 预设，使用 `宽*高` 像素格式 |
| `enable_base64_output` | `enable_base64_output`   | 否   | false                     | 开启后返回 Base64 图片，工作机解码保存   |

静态 Schema 的参数排序列包含 `images`。请求属性和端点文档均未定义该字段。模型页和端点文档给出 `generateImage`，模型页指定用 `prediction` 查询。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.5.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.5.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4.5.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4.5/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.5#usage-examples)

```json
{
  "model": "bytedance/seedream-v4.5",
  "prompt": "为城市读书节设计一张竖版海报，暖黄色纸张纹理，顶部标题留白，底部是一摞打开的书。",
  "size": "3520*4704",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与尺寸位于默认区。Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
