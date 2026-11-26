# MiniMax H3 Max 图生视频

Atlas Cloud 模型 ID 为 `minimax/h3-max/image-to-video`。提示词描述画面动作，首帧与尾帧可分别约束视频的起点和结尾。[官方 API 与输入 Schema](https://www.atlascloud.ai/models/minimax/h3-max/image-to-video)

## 字段和请求

| ComfyShop 字段     | Atlas 参数         | 必填 | 初始值     | 说明                                  |
| ------------------ | ------------------ | ---- | ---------- | ------------------------------------- |
| 工作机配置         | `model`            | 是   | 模型 ID    | 从 `execution.config.model` 读取      |
| `first_frame`      | `image`            | 否   | 用户上传   | 首帧图片                              |
| `last_frame`       | `end_image`        | 否   | 用户上传   | 尾帧图片                              |
| `prompt`           | `prompt`           | 是   | 用户填写   | 描述动作或镜头运动                    |
| `duration_seconds` | `duration`         | 是   | `8`        | 5–15 秒的整数                         |
| `resolution`       | `resolution`       | 是   | `768P`     | `480P`、`768P`、`1440p-sr` 或 `4k-sr` |
| `aspect_ratio`     | `ratio`            | 否   | `adaptive` | 仅支持自适应                          |
| `expand_prompt`    | `prompt_expansion` | 否   | `false`    | 生成前扩写提示词                      |

首尾帧支持 PNG、JPEG 和 WebP。工作机用 `uploadMedia` 将各素材转为 URL，写入对应的请求字段，空槽会省略。直接调用 Atlas API 时也可以提供 Base64。[素材上传文档](https://www.atlascloud.ai/docs/upload-files)

工作机凭 `Authorization: Bearer <API_KEY>` 调用 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。

```json
{
  "model": "minimax/h3-max/image-to-video",
  "prompt": "微风吹动纸灯笼，镜头缓慢拉远。",
  "image": "https://example.com/start.png",
  "end_image": "https://example.com/end.png",
  "duration": 8,
  "resolution": "768P",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

工作机保存提交返回的 `data.id`，轮询 `GET /api/v1/model/prediction/{id}`，完成后下载 `data.outputs` 中的视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## 参数布局与译文

首尾帧、提示词、时长与分辨率在默认区。提示词扩写在高级区，自适应比例在隐藏区。工作流标识为 `minimax-h3-max-image-to-video`。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../../docs/deployment.md#官方工作机)
