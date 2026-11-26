# Qwen Image 2.0 图片编辑

根据提示词编辑一至三张参考图。 Atlas Cloud 模型 ID 为 `qwen/qwen-image-2.0/edit`。[官方模型 API](https://www.atlascloud.ai/models/qwen/qwen-image-2.0/edit)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段                                                        | 必填 | 默认值                     | 输入约定                                                              |
| ---------- | --------------------------------------------------------------------- | ---- | -------------------------- | --------------------------------------------------------------------- |
| `model`    | `execution.config.model`                                              | 是   | `qwen/qwen-image-2.0/edit` | 工作机从执行配置读取                                                  |
| `images`   | `reference_image_1` 至 `reference_image_3`、`reference_image_sources` | 是   | —                          | 按顺序提供 1 至 3 张图。支持上传、公开 HTTP(S) 地址或 Base64 数据 URI |
| `prompt`   | `prompt`                                                              | 是   | —                          | 中文或英文，最多 800 字符                                             |
| `size`     | `size`                                                                | 否   | 由模型决定                 | `宽*高`，每边 512 至 2,048 像素                                       |
| `seed`     | `seed`                                                                | 否   | `-1`                       | `-1` 为随机。固定种子为 0 至 2,147,483,647 的整数                     |

静态 Schema 的通用响应示例使用了其他模型名。请求采用模型卡、端点标题和官方示例一致的 ID `qwen/qwen-image-2.0/edit`。Atlas 的字段描述提及 6 张参考图。工作流采用端点 Schema 的 `minItems: 1` 与 `maxItems: 3`。上传支持 JPEG、PNG、WebP、BMP、TIFF 和 GIF，每张最多 10 MB，推荐每边 384 至 3,072 像素。[Qwen 官方素材规范](https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-api)

[官方 Schema](https://static.atlascloud.ai/model/schema/qwen-qwen-image-2.0-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/qwen-qwen-image-2.0-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/qwen-qwen-image-2.0-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/qwen/qwen-image-2.0-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/qwen/qwen-image-2.0/edit#usage-examples)

```json
{
  "model": "qwen/qwen-image-2.0/edit",
  "images": ["https://static.atlascloud.ai/media/images/72174e0336226b0de69452c18711bca6.jpg"],
  "prompt": "把背景改成浅绿色，保留主体形状。",
  "size": "1024*1024",
  "seed": -1
}
```

从响应取 `id` 或 `data.id`，优先轮询模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`。遇到 404 或 405 时使用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按返回顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括参考图和提示词。高级参数包括输出尺寸、随机种子和参考图来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
