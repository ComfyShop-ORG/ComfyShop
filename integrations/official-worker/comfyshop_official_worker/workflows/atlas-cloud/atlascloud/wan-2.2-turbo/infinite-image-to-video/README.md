# Atlas Cloud Wan 2.2 Turbo 无限图生视频

从一张起始图生成连续的视频，按顺序执行 1 至 6 段提示词，每段 5 秒。 Atlas Cloud 模型 ID 为 `atlascloud/wan-2.2-turbo/infinite-image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/infinite-image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                                             | 输入约定                                                      |
| ------------ | ------------------------------------- | ---- | -------------------------------------------------- | ------------------------------------------------------------- |
| `model`      | `execution.config.model`              | 是   | `atlascloud/wan-2.2-turbo/infinite-image-to-video` | 工作机从执行配置读取                                          |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | 无                                                 | 上传起始图，或填写公开 URL、Base64 数据网址                   |
| `prompt`     | `prompt`                              | 是   | 官方示例                                           | 每行一个片段，工作机按行转为 1 至 6 项的 `string[]`，跳过空行 |
| `resolution` | `resolution`                          | 否   | `720p`                                             | `480p`、`720p` 或 `1080p`，后处理为每秒 30 帧                 |
| `duration`   | `duration`                            | 否   | 5                                                  | 每段固定 5 秒，合计 5 至 30 秒                                |
| `seed`       | `seed`                                | 否   | -1                                                 | 整数，-1 使用随机种子                                         |

表单保留 Schema 中可编辑的英文例句。每行对应一个视频片段，工作机保留顺序。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-wan-2.2-turbo-infinite-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-wan-2.2-turbo-infinite-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-wan-2.2-turbo-infinite-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/wan-2.2-turbo-infinite-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/infinite-image-to-video#usage-examples)

```json
{
  "model": "atlascloud/wan-2.2-turbo/infinite-image-to-video",
  "image": "https://example.com/cat.png",
  "prompt": ["小猫穿过草地，镜头在地面高度跟拍。", "小猫在岩石边停下，镜头缓慢推近。"],
  "resolution": "720p",
  "duration": 5,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、分段提示词和分辨率位于默认区。图片来源和种子位于高级区。工作机提交隐藏的固定单段时长。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
