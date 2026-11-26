# 可灵 4.0 Flash 图生视频

用一张起始图生成 3 至 20 秒的 720p 视频。可用提示词指定动作、场景变化和运镜。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0-flash/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                    | 输入约定                                                                               |
| ------------ | ------------------------------------- | ---- | ----------------------------------------- | -------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `kwaivgi/kling-v4.0-flash/image-to-video` | 工作机从执行配置读取                                                                   |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                        | JPEG 或 PNG，最多 30 MB，每边至少 300 像素，宽高比 2:5 至 5:2。支持上传、URL 和 Base64 |
| `prompt`     | `prompt`                              | 否   | 官方示例                                  | 描述动作、场景变化和镜头。英文最多 26,000 字符，非英文最多 11,000                      |
| `duration`   | `duration`                            | 否   | 10                                        | 3 至 20 秒的整数                                                                       |
| `resolution` | `resolution`                          | 否   | `720p`                                    | 固定 `720p`                                                                            |

表单保留同一条官方示例提示词，用户可以编辑或清空。工作机检查提示词的总长度，Atlas 检查语言对应的上限。Base64 来源使用 ComfyShop 单字段 4 MiB 上限。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-flash-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-flash-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-flash-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0-flash/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v4.0-flash/image-to-video",
  "image": "https://example.com/garden.jpg",
  "prompt": "镜头缓慢推向庭院中央，树叶在微风中轻轻摆动。",
  "duration": 10,
  "resolution": "720p"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词和时长位于默认区。图片来源位于高级区。固定分辨率由工作机提交。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
