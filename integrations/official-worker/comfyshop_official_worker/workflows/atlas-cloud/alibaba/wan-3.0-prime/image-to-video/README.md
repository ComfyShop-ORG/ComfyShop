# Wan 3.0 Prime 图生视频

用起始图与提示词生成视频，结束图可选。 Atlas Cloud 模型 ID 为 `alibaba/wan-3.0-prime/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                 | 输入约定                                                                         |
| ------------ | ------------------------------------- | ---- | -------------------------------------- | -------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `alibaba/wan-3.0-prime/image-to-video` | 工作机从执行配置读取                                                             |
| `prompt`     | `prompt`                              | 是   | 无                                     | 描述动作、运镜和画面变化，最多 20,000 字符                                       |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                     | 上传起始帧或填写公开图片 URL                                                     |
| `last_image` | `last_frame` 或 `last_frame_source`   | 否   | 无                                     | 上传结束帧或填写公开图片 URL，限制与起始帧相同                                   |
| `resolution` | `resolution`                          | 否   | `1080p`                                | 原生 `480p`、`720p`、`1080p`。ESR `720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `duration`   | `duration`                            | 否   | 5                                      | 2 至 30 秒，`-1` 为自动时长                                                      |
| `audio`      | `audio`                               | 否   | true                                   | 控制是否生成音轨                                                                 |
| `seed`       | `seed`                                | 否   | 由模型决定                             | 整数。`-1` 使用随机种子，留空时省略                                              |

首尾图可用 JPEG、无透明通道的 PNG、BMP 或 WebP。宽高各 240 至 8000 像素，长短边比例最多 8:1，每张最多 20 MB。工作机将上传图转换成素材地址，并按 Schema 提交小写的分辨率值。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-3.0-prime-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-3.0-prime-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-3.0-prime-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/image-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-3.0-prime/image-to-video",
  "prompt": "让图中的纸船沿水面向前漂，镜头贴近水面跟随。",
  "image": "https://example.com/boat-start.jpg",
  "last_image": "https://example.com/boat-end.jpg",
  "resolution": "1080p",
  "duration": 5,
  "audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首尾帧上传、分辨率和时长位于默认区。图片地址、音频与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
