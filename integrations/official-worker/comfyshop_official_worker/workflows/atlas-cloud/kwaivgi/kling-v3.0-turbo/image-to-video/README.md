# 可灵 3.0 Turbo 图生视频

用起始图生成 3 至 15 秒的视频，可用提示词引导动作和运镜。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v3.0-turbo/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-turbo/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                    | 输入约定                                                                                    |
| ------------ | ------------------------------------- | ---- | ----------------------------------------- | ------------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `kwaivgi/kling-v3.0-turbo/image-to-video` | 工作机从执行配置读取                                                                        |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                        | JPEG 或 PNG，每边至少 300 像素，宽高比 1:2.5 至 2.5:1，上传最多 50 MB。也可使用公开图片 URL |
| `prompt`     | `prompt`                              | 否   | 省略                                      | 描述动作、场景变化和镜头，留空时省略                                                        |
| `duration`   | `duration`                            | 否   | 5                                         | 3 至 15 秒，整数枚举                                                                        |
| `resolution` | `resolution`                          | 否   | `1080p`                                   | `720p` 或 `1080p`                                                                           |

模型 API 页与当前静态 Schema 标注图片上限为 50 MB，端点参考另标注 10 MB。工作机采用前两处一致的值。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v3.0-turbo-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v3.0-turbo-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v3.0-turbo-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v3.0-turbo-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-turbo/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v3.0-turbo/image-to-video",
  "image": "https://example.com/coast.jpg",
  "prompt": "镜头沿海边小路缓慢向前，远处的树叶随风摆动。",
  "duration": 5,
  "resolution": "1080p"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率和时长位于默认区。图片 URL 位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
