# Seedream v4.5 图像编辑

按提示词修改参考图，提供 2K 与 4K 成品尺寸。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.5/edit`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4.5/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                         | 输入约定                                 |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------------ | ---------------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v4.5/edit` | 工作机从执行配置读取                     |
| `prompt`               | `prompt`                                             | 是   | 无                             | 描述编辑内容，可按提交顺序引用参考图     |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 是   | 无                             | Atlas 接口接受 1 至 10 项                |
| `size`                 | `size`                                               | 否   | `2048*2048`                    | 16 个 2K、4K 预设，使用 `宽*高` 像素格式 |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                          | 开启后返回 Base64 图片，工作机解码保存   |

工作机将直接上传的文件转成素材 URL。高级区可逐行填入公开图片地址或按 BytePlus 模型文档提供 Base64 data URL，文本字段上限为 4 MiB。先按槽位发送上传文件，再按行发送文本素材。参考图上限使用 Atlas Schema。[BytePlus 图像 API](https://docs.byteplus.com/en/docs/ModelArk/image-generation-api) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.5-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.5-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4.5-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例链接改成实际素材。静态 Schema 的路径列为 `generateVideo` 和 `result`，工作机依据端点文档和模型示例使用 `generateImage` 及 `prediction`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4.5-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.5/edit#usage-examples)

```json
{
  "model": "bytedance/seedream-v4.5/edit",
  "prompt": "保持干花的构图，将桌面颜色改成暖灰，保留自然光影。",
  "images": ["https://example.com/dried-flowers.jpg"],
  "size": "2048*2048",
  "enable_base64_output": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图和尺寸位于默认区。其余参考图、素材地址及 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
