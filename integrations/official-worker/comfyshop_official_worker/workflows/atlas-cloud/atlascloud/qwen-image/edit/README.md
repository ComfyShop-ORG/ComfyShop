# Atlas Cloud Qwen Image 图像编辑

用文字指令编辑已有图片，可增删元素、调整物体或替换画面中的文字。 Atlas Cloud 模型 ID 为 `atlascloud/qwen-image/edit`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/qwen-image/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段            | 必填 | 默认值                       | 输入约定                               |
| ---------------------- | ------------------------- | ---- | ---------------------------- | -------------------------------------- |
| `model`                | `execution.config.model`  | 是   | `atlascloud/qwen-image/edit` | 工作机从执行配置读取                   |
| `image`                | `image` 或 `image_source` | 是   | 无                           | 上传原图或填写一个可公开访问的图片 URL |
| `prompt`               | `prompt`                  | 是   | 无                           | 描述需要修改的画面和文字               |
| `seed`                 | `seed`                    | 否   | -1                           | 整数，-1 使用随机种子                  |
| `enable_sync_mode`     | `enable_sync_mode`        | 否   | `false`                      | 开启后优先读取提交响应中的成品         |
| `enable_base64_output` | `enable_base64_output`    | 否   | `false`                      | 开启后读取并保存 Base64 图片数据       |

工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。静态示例数据含 `output_format`，当前模型 API 参数表、端点文档和请求 Schema 均只列出上表字段。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-qwen-image-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-qwen-image-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-qwen-image-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/qwen-image-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/qwen-image/edit#usage-examples)

```json
{
  "model": "atlascloud/qwen-image/edit",
  "image": "https://example.com/storefront.png",
  "prompt": "将招牌上的文字替换为“山间书店”，保留文字位置和光线。",
  "seed": -1,
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图和编辑指令位于默认区。原图 URL、种子、同步响应与 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
