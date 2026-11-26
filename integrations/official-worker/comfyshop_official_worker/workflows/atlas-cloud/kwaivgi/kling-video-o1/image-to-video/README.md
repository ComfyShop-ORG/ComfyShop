# 可灵 O1 图生视频

用起始图生成 5 或 10 秒的 1080p 视频，可指定结束帧。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-video-o1/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-video-o1/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                  | 输入约定                     |
| ------------ | ------------------------------------- | ---- | --------------------------------------- | ---------------------------- |
| `model`      | `execution.config.model`              | 是   | `kwaivgi/kling-video-o1/image-to-video` | 工作机从执行配置读取         |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                      | 起始图，支持上传或公开 URL   |
| `last_image` | `last_frame` 或 `last_frame_source`   | 否   | 省略                                    | 结束图，支持上传或公开 URL   |
| `prompt`     | `prompt`                              | 是   | 无                                      | 描述主体动作、场景变化和镜头 |
| `duration`   | `duration`                            | 否   | 5                                       | `5` 或 `10` 秒               |

成品输出 1080p，画面比例随起始图。静态示例带有 `aspect_ratio`，当前模型参数和模型说明将比例交给起始图决定。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-video-o1-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-video-o1-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-video-o1-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-video-o1-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-video-o1/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-video-o1/image-to-video",
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
