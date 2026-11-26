# Atlas Cloud Wan 2.2 图生视频

将一张起始图转成 3 至 10 秒的视频，可调整画面动作和镜头。 Atlas Cloud 模型 ID 为 `atlascloud/wan-2.2/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/wan-2.2/image-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                        | 必填 | 默认值                              | 输入约定                                                     |
| ----------------- | ------------------------------------- | ---- | ----------------------------------- | ------------------------------------------------------------ |
| `model`           | `execution.config.model`              | 是   | `atlascloud/wan-2.2/image-to-video` | 工作机从执行配置读取                                         |
| `image`           | `first_frame` 或 `first_frame_source` | 是   | 无                                  | 上传起始图，由工作机换成素材 URL，或填写可公开访问的图片 URL |
| `prompt`          | `prompt`                              | 是   | 无                                  | 描述需要的画面动作和镜头                                     |
| `negative_prompt` | `negative_prompt`                     | 否   | 空字符串                            | 描述希望避开的画面元素，空值时省略                           |
| `resolution`      | `resolution`                          | 否   | `480p`                              | `480p` 或 `720p`，720p 经超分处理                            |
| `duration`        | `duration`                            | 否   | 5                                   | 3 至 10 秒，整数                                             |
| `seed`            | `seed`                                | 否   | -1                                  | 整数，-1 使用随机种子                                        |

官方模型说明标注输出为每秒 30 帧。工作机按模型页的示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-wan-2.2-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-wan-2.2-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-wan-2.2-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/wan-2.2-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/wan-2.2/image-to-video#usage-examples)

```json
{
  "model": "atlascloud/wan-2.2/image-to-video",
  "image": "https://example.com/bicycle.jpg",
  "prompt": "镜头跟随自行车沿海岸缓慢移动。",
  "negative_prompt": "镜头抖动",
  "duration": 5,
  "resolution": "480p",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率和时长位于默认区。图片来源、负面提示词和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
