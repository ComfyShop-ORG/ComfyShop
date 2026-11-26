# HappyHorse 1.0 参考生视频

用一至九张参考图和提示词引导视频中的主体、场景或风格。 Atlas Cloud 模型 ID 为 `alibaba/happyhorse-1.0/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/reference-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                                      | 必填 | 默认值                                      | 输入约定                                                                                          |
| ------------ | --------------------------------------------------- | ---- | ------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`                            | 是   | `alibaba/happyhorse-1.0/reference-to-video` | 工作机从执行配置读取                                                                              |
| `prompt`     | `prompt`                                            | 是   | 无                                          | 描述目标视频及参考图的用途，最多 2,500 字符                                                       |
| `images`     | `reference_1` 至 `reference_9`、`reference_sources` | 是   | 无                                          | 一至九个公开图片 URL。JPEG、PNG、BMP 或 WebP，短边至少 400 像素且至少为长边的 40%，单张最多 10 MB |
| `resolution` | `resolution`                                        | 否   | `1080p`                                     | `720p` 或 `1080p`                                                                                 |
| `ratio`      | `ratio`                                             | 否   | `16:9`                                      | `16:9`、`9:16`、`1:1`、`4:3` 或 `3:4`                                                             |
| `duration`   | `duration`                                          | 否   | 5                                           | 3 至 15 秒的整数                                                                                  |
| `seed`       | `seed`                                              | 否   | -1                                          | 整数，范围 -1 至 2147483647。-1 使用随机种子                                                      |

工作机先将上传图转换成素材地址，再按行追加手工填写的公开 URL。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-happyhorse-1.0-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-happyhorse-1.0-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-happyhorse-1.0-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/reference-to-video#usage-examples)

```json
{
  "model": "alibaba/happyhorse-1.0/reference-to-video",
  "prompt": "沿用参考图里的玻璃温室，镜头从门口转向右侧花架。",
  "images": ["https://example.com/greenhouse.webp"],
  "resolution": "1080p",
  "ratio": "3:4",
  "duration": 8,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图、分辨率、比例和时长位于默认区。其余图片、公开地址与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
