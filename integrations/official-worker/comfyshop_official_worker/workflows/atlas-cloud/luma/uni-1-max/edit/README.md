# Luma Uni 1 Max 图片编辑

根据提示词修改一张图片，并设置成品宽高比和格式。 Atlas Cloud 模型 ID 为 `luma/uni-1-max/edit`。[官方模型 API](https://www.atlascloud.ai/models/luma/uni-1-max/edit)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段                        | 必填 | 默认值                | 输入约定                                            |
| --------------- | ------------------------------------- | ---- | --------------------- | --------------------------------------------------- |
| `model`         | `execution.config.model`              | 是   | `luma/uni-1-max/edit` | 工作机从执行配置读取                                |
| `image`         | `input_image` 或 `input_image_source` | 是   | —                     | 上传、公开 URL、Base64 或 `asset://`                |
| `prompt`        | `prompt`                              | 是   | Schema 提供可编辑示例 | 描述编辑内容及要保留的部分                          |
| `aspect_ratio`  | `aspect_ratio`                        | 否   | `16:9`                | `1:1`、`3:4`、`4:3`、`9:16`、`16:9`、`9:21`、`21:9` |
| `output_format` | `output_format`                       | 否   | `jpeg`                | `jpeg` 或 `png`                                     |

原图支持 JPEG、PNG、WebP 和静态 GIF。工作机可上传原图，也可原样传递公开 URL、Base64 或 Atlas 素材引用。大尺寸的 Base64 素材可直接上传。[Luma 素材格式](https://docs.agents.lumalabs.ai/guides/faq/)

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-uni-1-max-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-uni-1-max-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-uni-1-max-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/luma/uni-1-max/edit#usage-examples)

```json
{
  "model": "luma/uni-1-max/edit",
  "image": "https://example.com/source.png",
  "prompt": "保留原有构图，让灯光更暖并增加薄雾。",
  "aspect_ratio": "16:9",
  "output_format": "jpeg"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序下载并保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原图、提示词、宽高比和输出格式。高级参数为原图来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
