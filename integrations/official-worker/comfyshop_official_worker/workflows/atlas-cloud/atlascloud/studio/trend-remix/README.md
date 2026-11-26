# Atlas Cloud Studio 热门视频改编

借鉴参考视频的结构、节奏和运镜，制作展示自己商品的新视频。 Atlas Cloud 模型 ID 为 `atlascloud/studio/trend-remix`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/trend-remix)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                      | 必填 | 默认值                          | 输入约定                                                                |
| ----------------- | ----------------------------------- | ---- | ------------------------------- | ----------------------------------------------------------------------- |
| `model`           | `execution.config.model`            | 是   | `atlascloud/studio/trend-remix` | 工作机从执行配置读取                                                    |
| `reference_video` | `reference_video` 或 `video_source` | 是   | 无                              | 一条 4 至 20 秒的 MP4 或 MOV，上传最多 20 MB。工作机组装为 URL 数组     |
| `product_image`   | `product_image` 或 `product_source` | 是   | 无                              | 一张商品图，上传最多 10 MB。工作机组装为 URL 数组                       |
| `model_image`     | `model_image` 或 `model_source`     | 否   | 省略                            | 一张模特图，上传最多 10 MB。工作机组装为 URL 数组                       |
| `user_prompt`     | `user_prompt`                       | 是   | 无                              | 描述品牌、卖点和视频风格                                                |
| `duration`        | `duration`                          | 否   | 跟随参考视频                    | 4 至 20 秒，整数枚举。选择跟随参考视频时省略字段                        |
| `ratio`           | `ratio`                             | 否   | `16:9`                          | `16:9`、`9:16`、`1:1`、`3:4` 或 `4:3`                                   |
| `resolution`      | `resolution`                        | 否   | `720p`                          | `480p`、`720p`、`1080p`、`720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `generate_audio`  | `generate_audio`                    | 否   | `yes`                           | `yes` 生成同期声，`no` 关闭                                             |
| `count`           | `count`                             | 否   | 1                               | `1` 或 `2` 条                                                           |

工作机保留三种素材字段的数组结构。省略 `duration` 后，Atlas 分析参考视频并生成相同长度的成品。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-trend-remix.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-trend-remix.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-trend-remix)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/studio-trend-remix/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/trend-remix#usage-examples)

```json
{
  "model": "atlascloud/studio/trend-remix",
  "reference_video": ["https://example.com/template.mp4"],
  "product_image": ["https://example.com/product.png"],
  "user_prompt": "展示随行杯的使用过程，参考视频的快切节奏和手持镜头。",
  "ratio": "9:16",
  "resolution": "720p",
  "generate_audio": "yes",
  "count": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

参考视频、商品图、模特图、创作指令、时长、比例和分辨率位于默认区。素材 URL、同期声和视频数量位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
