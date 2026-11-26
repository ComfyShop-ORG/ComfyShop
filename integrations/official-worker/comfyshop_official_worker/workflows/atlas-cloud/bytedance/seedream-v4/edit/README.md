# Seedream v4 图像编辑

根据提示词修改参考图，支持填写成品宽高。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                       | 输入约定                               |
| ---------------------- | ---------------------------------------------------- | ---- | ---------------------------- | -------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v4/edit` | 工作机从执行配置读取                   |
| `prompt`               | `prompt`                                             | 是   | 无                           | 说明需要修改和保留的内容               |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                           | 1 至 10 个 URL 或 Base64 data URL      |
| `size`                 | `size`                                               | 否   | `2048*2048`                  | `宽*高` 像素格式，每边 1024 至 4096    |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                        | 开启后返回 Base64 图片，工作机解码保存 |

工作机把直接上传的参考图转换为素材 URL，再按行追加文本区的公开 URL 或 Base64 data URL，文本字段上限为 4 MiB。Atlas 静态 Schema 把尺寸标为网页隐藏，端点保留该参数，所以在高级区开放。静态示例还有 `enable_sync_mode`，端点请求定义采用上表四项。模型 API 的查询示例使用 `prediction`。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例链接改成实际素材。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4/edit#usage-examples)

```json
{
  "model": "bytedance/seedream-v4/edit",
  "prompt": "把参考图中的蓝色花器改成半透明灰玻璃，保留桌面、背景与光向。",
  "images": ["https://example.com/vase.png"],
  "size": "2048*1536"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词与首张参考图位于默认区。其余参考图、素材地址、尺寸和 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
