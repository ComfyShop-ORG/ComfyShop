# Atlas Cloud 照片清理

减少静态图片的灰尘、细划痕、噪点和重复的微细纹理，保留主体与构图。Atlas Cloud 模型 ID 为 `atlascloud/photo-cleanup`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/photo-cleanup)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                     | 输入约定                                             |
| --------------- | ------------------------ | ---- | -------------------------- | ---------------------------------------------------- |
| `model`         | `execution.config.model` | 是   | `atlascloud/photo-cleanup` | 工作机从执行配置读取                                 |
| `image`         | `image`                  | 是   | 无                         | 上传一张静态图片，工作机将其转换为供应商可访问的 URL |
| `output_format` | `output_format`          | 否   | `png`                      | 允许 `png`、`jpeg`、`webp` 和 `jpg`                  |

处理过程依次减少灰尘和噪点。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-photo-cleanup.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-photo-cleanup.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-photo-cleanup.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。示例地址替换为原图的可访问 URL。

```json
{
  "model": "atlascloud/photo-cleanup",
  "image": "https://example.com/old-photo.webp",
  "output_format": "png"
}
```

取得预测编号，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `outputs` 下载清理后的图片。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/photo-cleanup#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图位于默认区，输出格式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
