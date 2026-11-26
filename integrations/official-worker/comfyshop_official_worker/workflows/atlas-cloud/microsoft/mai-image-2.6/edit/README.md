# MAI-Image 2.6 图片编辑

根据提示词编辑图片，可用多张参考图指导内容、布局或风格。 Atlas Cloud 模型 ID 为 `microsoft/mai-image-2.6/edit`。[官方模型 API](https://www.atlascloud.ai/models/microsoft/mai-image-2.6/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                                          | 必填 | 默认值                         | 输入约定                                        |
| ---------------------- | ----------------------------------------------------------------------- | ---- | ------------------------------ | ----------------------------------------------- |
| `model`                | `execution.config.model`                                                | 是   | `microsoft/mai-image-2.6/edit` | 工作机从执行配置读取                            |
| `reference_images`     | `reference_image_1` 至 `reference_image_5` 与 `reference_image_sources` | 是   | —                              | 1 至 5 张 JPEG 或 PNG，可上传、填 URL 或 Base64 |
| `prompt`               | `prompt`                                                                | 是   | —                              | 非空文本，Atlas 上下文上限为 32,000 个令牌      |
| `size`                 | `size`                                                                  | 否   | `default`                      | `default` 沿用输入图宽高比，`auto` 自动构图     |
| `enable_web_search`    | `enable_web_search`                                                     | 否   | `false`                        | 通过网络搜索参考现实人物、地点或事件            |
| `enable_base64_output` | `enable_base64_output`                                                  | 否   | `false`                        | Base64 结果由工作机解码后保存                   |
| `enable_sync_mode`     | `enable_sync_mode`                                                      | 否   | `false`                        | 在提交响应中等待并取成品                        |

每张参考图的总像素须小于 1,376,256。工作机按槽位顺序收集上传图片，再追加每一行的公开 URL、Base64 Data URI 或原始 Base64。工作机校验已上传图像的像素总数，Atlas 校验外部素材与令牌上限。

[官方 Schema](https://static.atlascloud.ai/model/schema/microsoft-mai-image-2.6-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/microsoft-mai-image-2.6-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/microsoft-mai-image-2.6-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/microsoft/mai-image-2.6/edit#usage-examples)

```json
{
  "model": "microsoft/mai-image-2.6/edit",
  "prompt": "晨雾穿过森林，柔和的光照亮长满苔藓的石墙。",
  "reference_images": ["https://example.com/source.png"],
  "size": "default",
  "enable_web_search": false,
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

开启同步且提交已返回成品时，工作机直接保存。异步时从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为参考图、提示词和输出尺寸。高级参数为参考图来源、网络搜索、Base64 成品和同步返回。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
