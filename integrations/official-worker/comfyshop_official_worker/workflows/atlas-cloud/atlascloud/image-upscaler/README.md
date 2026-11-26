# Atlas Cloud 图片放大

将一张已有图片按 1 至 4 倍处理。Atlas Cloud 模型 ID 为 `atlascloud/image-upscaler`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/image-upscaler)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                      | 输入约定                                     |
| --------------- | ------------------------ | ---- | --------------------------- | -------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `atlascloud/image-upscaler` | 工作机从执行配置读取                         |
| `image`         | `image`                  | 是   | 无                          | 上传一张图片，工作机转换为供应商可访问的 URL |
| `outscale`      | `outscale`               | 否   | 1                           | 1 至 4 的放大倍数，可用小数                  |
| `output_format` | `output_format`          | 否   | `jpeg`                      | 允许 `jpeg`、`png`、`webp` 和 `jpg`          |

倍数作用于原图宽高。模型基于 Real-ESRGAN 处理图像。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-image-upscaler.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-image-upscaler.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-image-upscaler.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。示例地址替换为原图的可访问 URL。

```json
{
  "model": "atlascloud/image-upscaler",
  "image": "https://example.com/source.png",
  "outscale": 2.5,
  "output_format": "png"
}
```

使用预测编号轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。任务完成后从 `outputs` 下载图片。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/image-upscaler#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图和放大倍数位于默认区，输出格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
