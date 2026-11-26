# Seedance v1 Pro 720p 图生视频

用起始图生成固定 720p 的视频，可选结束图。 Atlas Cloud 模型 ID 为 `bytedance/seedance-v1-pro-i2v-720p`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-v1-pro-i2v-720p)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                        | 必填 | 默认值                               | 输入约定                                           |
| -------------- | ------------------------------------- | ---- | ------------------------------------ | -------------------------------------------------- |
| `model`        | `execution.config.model`              | 是   | `bytedance/seedance-v1-pro-i2v-720p` | 工作机从执行配置读取                               |
| `image`        | `first_frame` 或 `first_frame_source` | 是   | 官方示例图                           | 起始图。JPEG 或 PNG，最多 10 MB，每边至少 300 像素 |
| `last_image`   | `last_frame` 或 `last_frame_source`   | 否   | 省略                                 | 结束图。JPEG 或 PNG，最多 10 MB，每边至少 300 像素 |
| `prompt`       | `prompt`                              | 否   | 官方示例                             | 描述动作、场景和镜头，最多 2,000 字符              |
| `aspect_ratio` | `aspect_ratio`                        | 否   | 省略                                 | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16`        |
| `duration`     | `duration`                            | 是   | 5                                    | 2 至 12 秒的整数                                   |
| `seed`         | `seed`                                | 否   | -1                                   | 整数，-1 使用随机种子                              |

720p 由模型 ID 指定。两帧可上传，也可填写公开 URL 或带媒体类型的 Base64 数据网址。ComfyShop 每个来源字段限制为 4 MiB。Atlas 的默认示例图见下方请求，可将地址填写到起始图来源。静态示例数据还列有 `camera_fixed`，工作流请求依据当前 Schema。静态 Schema 列有旧的 `result` 路径，模型 API 示例使用 `prediction`。[火山方舟 Seedance 接口说明](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-v1-pro-i2v-720p.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-v1-pro-i2v-720p.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-v1-pro-i2v-720p.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-v1-pro-i2v-720p/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-v1-pro-i2v-720p#usage-examples)

```json
{
  "model": "bytedance/seedance-v1-pro-i2v-720p",
  "image": "https://static.atlascloud.ai/media/images/1750742499545258689_aeXmGbsM.jpg",
  "prompt": "镜头靠近主体，捕捉随微风产生的轻微动作。",
  "duration": 5,
  "seed": -1
}
```

从响应取 `data.id` 或顶层 `id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按成品数组顺序保存视频，读取预测接口的 `outputs` 或此模型 Schema 的 `output`。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、结束图、提示词、画面比例和成品时长位于默认区。种子和两帧来源位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
