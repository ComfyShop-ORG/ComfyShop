# Z-Image Turbo 文生图

根据中文或英文提示词快速生成图片，可选择提示词改写。 Atlas Cloud 模型 ID 为 `z-image/turbo`。[官方模型 API](https://www.atlascloud.ai/models/z-image/turbo)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段           | 必填 | 默认值          | 输入约定                           |
| ---------------------- | ------------------------ | ---- | --------------- | ---------------------------------- |
| `model`                | `execution.config.model` | 是   | `z-image/turbo` | 工作机从执行配置读取               |
| `prompt`               | `prompt`                 | 是   | —               | 支持中文或英文场景描述             |
| `size`                 | `size`                   | 否   | `1024*1536`     | `宽*高`，每边 512 至 2,048 像素    |
| `prompt_extend`        | `prompt_extend`          | 否   | `false`         | 启用提示词改写                     |
| `seed`                 | `seed`                   | 否   | `-1`            | `-1` 为随机，指定整数可复用种子    |
| `enable_sync_mode`     | `enable_sync_mode`       | 否   | `false`         | 等待上传完成并在提交响应中返回成品 |
| `enable_base64_output` | `enable_base64_output`   | 否   | `false`         | 返回 Base64 图像                   |

启用同步返回时，工作机可直接处理提交响应中的成品。启用 Base64 时，工作机解码并保存图片。

[官方 Schema](https://static.atlascloud.ai/model/schema/z-image-turbo.json) · [官方示例数据](https://static.atlascloud.ai/model/example/z-image-turbo.json) · [模型说明](https://static.atlascloud.ai/model/readme/z-image-turbo.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/z-image/turbo/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/z-image/turbo#usage-examples)

```json
{
  "model": "z-image/turbo",
  "prompt": "清晨光线穿过大窗户，照在木桌上的白色花瓶。",
  "size": "1024*1536",
  "seed": -1,
  "prompt_extend": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括提示词和输出尺寸。高级参数包括提示词改写、随机种子、同步返回和 Base64 成品。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
