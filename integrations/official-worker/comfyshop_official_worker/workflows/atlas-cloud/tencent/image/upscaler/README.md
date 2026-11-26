# 腾讯云图片超分

通过腾讯云 MPS 提高图片分辨率和细节。Atlas Cloud 模型 ID 为 `tencent/image/upscaler`。[官方模型 API](https://www.atlascloud.ai/models/tencent/image/upscaler)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段           | 必填           | 默认值                   | 输入约定                                                                 |
| ---------------- | ------------------------ | -------------- | ------------------------ | ------------------------------------------------------------------------ |
| `model`          | `execution.config.model` | 是             | `tencent/image/upscaler` | 工作机从执行配置读取                                                     |
| `image_url`      | `image`                  | 是             | 无                       | 上传一张 JPEG 或 PNG，工作机上传到 Atlas 并发送素材 URL                  |
| `type`           | `type`                   | 否             | `ultra`                  | `standard` 通用、`super` 面向生成图、`ultra` 增强细节、`fidelity` 高保真 |
| `mode`           | `mode`                   | 否             | `percent`                | `percent` 按倍数、`aspect` 等比适配、`fixed` 固定尺寸                    |
| `percent`        | `percent`                | 按倍数模式必填 | 2                        | 1 至 10 倍，步长 0.1                                                     |
| `width`          | `width`                  | 否             | 无                       | 等比或固定模式的目标宽度，至少 1 像素                                    |
| `height`         | `height`                 | 否             | 无                       | 等比或固定模式的目标高度，至少 1 像素                                    |
| `long_side`      | `long_side`              | 否             | 无                       | 等比或固定模式的目标长边，至少 1 像素                                    |
| `short_side`     | `short_side`             | 否             | 无                       | 等比或固定模式的目标短边，至少 1 像素                                    |
| `encode_format`  | `encode_format`          | 否             | `JPEG`                   | 支持 `JPEG`、`PNG`、`WEBP` 和 `BMP`                                      |
| `encode_quality` | `encode_quality`         | 否             | 80                       | JPEG 或 WebP 的编码质量，1 至 100                                        |
| `output_dir`     | `output_dir`             | 否             | 自动分配                 | 腾讯云 COS 输出目录                                                      |

等比或固定模式请设置目标宽高或长短边。腾讯云原生处理以宽高优先，并文档化了 4096 像素的原生上限。Atlas Schema 对四个尺寸字段给出最小值。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-image-upscaler.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-image-upscaler.json) · [腾讯云超分参数](https://cloud.tencent.com/document/api/862/37615#AdvancedSuperResolutionConfig)

## API 调用

将以下固定尺寸示例发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "tencent/image/upscaler",
  "image_url": "https://example.com/source.png",
  "type": "ultra",
  "mode": "fixed",
  "width": 1280,
  "height": 720,
  "encode_format": "PNG"
}
```

取预测编号，按该模型 Schema 轮询 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`。模型 API 页面也给出了通用 `prediction/{id}` 地址，工作机会在前者返回 404 或 405 时使用这个地址续查同一任务。完成后从 `outputs` 下载超分后的图片。[模型 API 页面](https://www.atlascloud.ai/models/tencent/image/upscaler#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原图、超分类型、缩放方式和放大倍数位于默认区。目标尺寸、编码与 COS 目录位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
