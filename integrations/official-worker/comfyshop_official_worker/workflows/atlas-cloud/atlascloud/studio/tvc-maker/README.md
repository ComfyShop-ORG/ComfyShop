# Atlas Cloud Studio 品牌广告片

用商品照片和品牌信息生成广告片，可选择模特照片、时长和画面比例。 Atlas Cloud 模型 ID 为 `atlascloud/studio/tvc-maker`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/tvc-maker)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                      | 必填 | 默认值                        | 输入约定                                                                |
| ---------------- | ----------------------------------- | ---- | ----------------------------- | ----------------------------------------------------------------------- |
| `model`          | `execution.config.model`            | 是   | `atlascloud/studio/tvc-maker` | 工作机从执行配置读取                                                    |
| `product_image`  | `product_image` 或 `product_source` | 是   | 无                            | 一张商品图，上传最多 10 MB，也可提供公开 URL。工作机组装为数组          |
| `model_image`    | `model_image` 或 `model_source`     | 否   | 省略                          | 一张模特图，上传最多 10 MB，也可提供公开 URL。工作机组装为数组          |
| `user_prompt`    | `user_prompt`                       | 是   | 无                            | 描述品牌、卖点、目标人群与调性                                          |
| `duration`       | `duration`                          | 否   | 10                            | 4 至 30 秒，整数枚举                                                    |
| `ratio`          | `ratio`                             | 否   | `16:9`                        | `16:9`、`9:16`、`1:1`、`3:4` 或 `4:3`                                   |
| `resolution`     | `resolution`                        | 否   | `720p`                        | `480p`、`720p`、`1080p`、`720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `generate_audio` | `generate_audio`                    | 否   | `yes`                         | `yes` 生成同期声，`no` 关闭                                             |
| `count`          | `count`                             | 否   | 1                             | `1` 或 `2` 条                                                           |

省略模特图时，Atlas 会按品牌调性设计角色。官方静态示例缺少商品图，下面的调用按当前请求 Schema 补齐。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-tvc-maker.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-tvc-maker-v2.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-tvc-maker)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/studio-tvc-maker/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/tvc-maker#usage-examples)

```json
{
  "model": "atlascloud/studio/tvc-maker",
  "product_image": ["https://example.com/desk-lamp.png"],
  "user_prompt": "为一款哑光台灯制作广告片，表现阅读时的柔和侧光，用稳定的近景突出旋钮和灯罩材质。",
  "duration": 15,
  "ratio": "16:9",
  "resolution": "720p",
  "generate_audio": "yes",
  "count": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

商品图、模特图、创作指令、时长、比例和分辨率位于默认区。素材 URL、同期声和视频数量位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
