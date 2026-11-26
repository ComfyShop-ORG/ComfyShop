# Atlas Cloud Studio 视频复刻

以参考视频的节奏、构图和运镜为模板，替换为自己的商品，并可提供模特图。 Atlas Cloud 模型 ID 为 `atlascloud/studio/video-clone`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/video-clone)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                      | 必填 | 默认值                          | 输入约定                                                       |
| ----------------- | ----------------------------------- | ---- | ------------------------------- | -------------------------------------------------------------- |
| `model`           | `execution.config.model`            | 是   | `atlascloud/studio/video-clone` | 工作机从执行配置读取                                           |
| `reference_video` | `reference_video` 或 `video_source` | 是   | 无                              | 2 至 30 秒的 MP4 或 MOV。上传或提供可公开访问的直链            |
| `product_image`   | `product_image` 或 `product_source` | 是   | 无                              | 一张商品图，组装为 URL 数组                                    |
| `model_image`     | `model_image` 或 `model_source`     | 否   | 省略                            | 可选的一张替换人物图，组装为 URL 数组                          |
| `user_prompt`     | `user_prompt`                       | 否   | 省略                            | 描述场景或氛围的微调，空值省略                                 |
| `resolution`      | `resolution`                        | 否   | `720p`                          | `480p`、`720p`、`720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `count`           | `count`                             | 否   | 1                               | `1`、`2`、`3` 或 `4`                                           |
| `duration`        | `duration`                          | 否   | 8                               | 参考视频的实际时长整数，用于计价。输出时长随参考视频           |

商品图和模特图各自使用一个素材槽，按 Studio 表单输入一张图并组装为数组。官方 Schema 将计价时长标记为隐藏参数，本工作流把它放在高级参数，方便在更换参考视频时填入实际时长。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-video-clone.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-video-clone.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-exact-clone)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/video-clone#usage-examples)

```json
{
  "model": "atlascloud/studio/video-clone",
  "reference_video": "https://example.com/template.mp4",
  "product_image": ["https://example.com/product.png"],
  "model_image": ["https://example.com/model.png"],
  "user_prompt": "保留原视频的运镜，改用暖色布光。",
  "resolution": "720p",
  "count": 1,
  "duration": 8
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考视频、商品图、模特图、调整说明和分辨率位于默认区。素材 URL、参考视频时长和数量位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
