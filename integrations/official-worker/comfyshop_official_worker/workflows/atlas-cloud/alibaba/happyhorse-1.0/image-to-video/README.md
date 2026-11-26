# HappyHorse 1.0 图生视频

用起始图生成视频，可用提示词引导动作、风格和场景。 Atlas Cloud 模型 ID 为 `alibaba/happyhorse-1.0/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                  | 输入约定                                                                                                |
| ------------ | ------------------------------------- | ---- | --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `alibaba/happyhorse-1.0/image-to-video` | 工作机从执行配置读取                                                                                    |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                      | 上传或填写公开图片 URL。JPEG、PNG、BMP 或 WebP，短边至少 300 像素，长短边比例最多 2.5:1，每张最多 10 MB |
| `prompt`     | `prompt`                              | 否   | 无                                      | 最多 2,500 字符，留空时省略                                                                             |
| `resolution` | `resolution`                          | 否   | `1080p`                                 | `720p` 或 `1080p`                                                                                       |
| `duration`   | `duration`                            | 否   | 5                                       | 3 至 15 秒的整数                                                                                        |
| `seed`       | `seed`                                | 否   | -1                                      | 整数，范围 -1 至 2147483647。-1 使用随机种子                                                            |

工作机将上传图转换成素材地址，提交 Schema 中的小写分辨率值。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-happyhorse-1.0-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-happyhorse-1.0-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-happyhorse-1.0-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/alibaba/happyhorse-1.0/image-to-video#usage-examples)

```json
{
  "model": "alibaba/happyhorse-1.0/image-to-video",
  "image": "https://example.com/greenhouse.png",
  "prompt": "镜头沿温室内的小路向前移动，花架上的叶片按微风的节奏摇动。",
  "resolution": "1080p",
  "duration": 5,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率与时长位于默认区。图片地址和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
