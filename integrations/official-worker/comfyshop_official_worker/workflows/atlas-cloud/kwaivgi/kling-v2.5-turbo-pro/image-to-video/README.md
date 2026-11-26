# 可灵 2.5 Turbo 专业版图生视频

用起始图和文字生成 5 或 10 秒的视频，可添加结束图引导过渡。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v2.5-turbo-pro/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v2.5-turbo-pro/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                        | 输入约定                                                                              |
| ------------ | ------------------------------------- | ---- | --------------------------------------------- | ------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `kwaivgi/kling-v2.5-turbo-pro/image-to-video` | 工作机从执行配置读取                                                                  |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                            | JPEG 或 PNG，每边至少 300 像素，宽高比 1:2.5 至 2.5:1，上传最多 50 MB，或提供公开 URL |
| `last_image` | `last_frame` 或 `last_frame_source`   | 否   | 省略                                          | 结束图，支持上传或公开 URL                                                            |
| `prompt`     | `prompt`                              | 是   | 无                                            | 描述主体动作、场景变化和镜头，最多 2,500 字符                                         |
| `duration`   | `duration`                            | 否   | 5                                             | `5` 或 `10` 秒                                                                        |

起始图和结束图对应视频首尾帧。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v2.5-turbo-pro-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v2.5-turbo-pro-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v2.5-turbo-pro-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v2.5-turbo-pro-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v2.5-turbo-pro/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v2.5-turbo-pro/image-to-video",
  "image": "https://example.com/start.jpg",
  "last_image": "https://example.com/end.jpg",
  "prompt": "镜头缓慢穿过植物走廊，从绿色叶片转向通透的玻璃屋顶。",
  "duration": 5
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、结束图、提示词和时长位于默认区。图片 URL 位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
