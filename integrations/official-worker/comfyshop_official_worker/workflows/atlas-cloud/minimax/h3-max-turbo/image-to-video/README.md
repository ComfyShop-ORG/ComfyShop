# MiniMax H3 Max Turbo 图生视频

从提示词和可选的首尾帧生成视频。Atlas Cloud 模型 ID 为 `minimax/h3-max-turbo/image-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-max-turbo/image-to-video)

## 官方参数

| Atlas 参数   | ComfyShop 字段           | 必填 | 默认值                                | 输入约定                   |
| ------------ | ------------------------ | ---- | ------------------------------------- | -------------------------- |
| `model`      | `execution.config.model` | 是   | `minimax/h3-max-turbo/image-to-video` | 工作机从执行配置读取       |
| `prompt`     | `prompt`                 | 是   | 由用户填写                            | 描述动作和镜头运动         |
| `image`      | `first_frame`            | 否   | 由用户上传                            | 起始图片                   |
| `end_image`  | `last_frame`             | 否   | 由用户上传                            | 结束图片                   |
| `duration`   | `duration_seconds`       | 是   | `8`                                   | 5 至 15 秒，按整数枚举提交 |
| `resolution` | `resolution`             | 是   | `768P`                                | `480P`、`768P`             |
| `ratio`      | `aspect_ratio`           | 否   | `adaptive`                            | 自适应比例，唯一枚举       |

首尾帧支持 PNG、JPEG 和 WebP。直接调用 API 可传公开 URL 或 Base64。工作机先用 `uploadMedia` 上传已提供的帧，再把返回的 URL 写入对应字段。留空的素材字段会省略。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-max-turbo-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-max-turbo-image-to-video.json) · [素材上传](https://www.atlascloud.ai/docs/en/upload-files)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "minimax/h3-max-turbo/image-to-video",
  "prompt": "镜头从陶瓷杯缓缓拉远，露出晨光下的木桌。",
  "image": "https://example.com/opening.png",
  "end_image": "https://example.com/ending.png",
  "duration": 8,
  "resolution": "768P",
  "ratio": "adaptive"
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 获取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-max-turbo/image-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/en/predictions)

## ComfyShop 同步

首尾帧、提示词、时长和分辨率位于默认区。自适应比例位于隐藏区。字段文案随展示语言切换，维护账号可通过「编辑参数」调整字段布局与默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
