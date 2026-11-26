# MAI-Image 2.5 Pro 文生图

根据提示词生成图片，可设置输出像素尺寸。 Atlas Cloud 模型 ID 为 `microsoft/mai-image-2.5-pro/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/microsoft/mai-image-2.5-pro/text-to-image)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值                                      | 输入约定                                   |
| ---------------------- | ------------------------ | ---- | ------------------------------------------- | ------------------------------------------ |
| `model`                | `execution.config.model` | 是   | `microsoft/mai-image-2.5-pro/text-to-image` | 工作机从执行配置读取                       |
| `prompt`               | `prompt`                 | 是   | —                                           | 非空文本，Atlas 上下文上限为 32,000 个令牌 |
| `size`                 | `size`                   | 否   | `1024*1024`                                 | `宽*高`                                    |
| `enable_base64_output` | `enable_base64_output`   | 否   | `false`                                     | Base64 结果由工作机解码后保存              |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | `false`                                     | 在提交响应中等待并取成品                   |

自定义尺寸每边 768 至 1,360 像素，像素总数 589,824 至 1,048,576。工作机在提交前校验像素尺寸，Atlas 校验令牌上限。

[官方 Schema](https://static.atlascloud.ai/model/schema/microsoft-mai-image-2.5-pro-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/microsoft-mai-image-2.5-pro-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/microsoft-mai-image-2.5-pro-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/microsoft/mai-image-2.5-pro/text-to-image#usage-examples)

```json
{
  "model": "microsoft/mai-image-2.5-pro/text-to-image",
  "prompt": "晨雾穿过森林，柔和的光照亮长满苔藓的石墙。",
  "size": "1360*768",
  "enable_base64_output": false,
  "enable_sync_mode": false
}
```

开启同步且提交已返回成品时，工作机直接保存。异步时从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词和输出尺寸。高级参数为 Base64 成品和同步返回。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
