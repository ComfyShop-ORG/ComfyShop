# MiniMax H3 Developer 图生视频

根据提示词生成视频，可上传首尾帧控制画面的起点和结尾。Atlas Cloud 模型 ID 为 `minimax/h3-developer/image-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-developer/image-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                                | 输入约定                            |
| ------------------ | ------------------------ | ---- | ------------------------------------- | ----------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-developer/image-to-video` | 工作机从执行配置读取                |
| `prompt`           | `prompt`                 | 是   | 由用户填写                            | 描述画面动作与运镜                  |
| `image`            | `first_frame`            | 否   | 由用户上传                            | 起始图片                            |
| `end_image`        | `last_frame`             | 否   | 由用户上传                            | 结束图片                            |
| `duration`         | `duration_seconds`       | 是   | `8`                                   | 4 至 15 秒的整数                    |
| `resolution`       | `resolution`             | 是   | `768P`                                | `480P`、`768P`、`1440p-sr`、`4k-sr` |
| `ratio`            | `aspect_ratio`           | 否   | `adaptive`                            | 唯一枚举为 `adaptive`               |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                               | 是否在生成前扩写提示词              |

首尾帧支持 PNG、JPEG 和 WebP。工作机上传素材并使用返回的 URL，省略空槽。直接调用 Atlas API 可传 URL 或 Base64。[素材上传](https://www.atlascloud.ai/docs/upload-files)

请求字段跟随 Atlas Schema 与 HTTP 示例。静态示例数据另有 `seed` 和 `num_inference_steps`，这两个字段的 Atlas 请求定义尚无文档说明。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-developer-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-developer-image-to-video.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "minimax/h3-developer/image-to-video",
  "prompt": "镜头缓慢上升，从河面的小船移向远处的拱桥。",
  "image": "https://example.com/opening.png",
  "end_image": "https://example.com/ending.png",
  "duration": 8,
  "resolution": "768P",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-developer/image-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

首尾帧、提示词、时长与分辨率位于默认区，扩写在高级区，自适应比例在隐藏区。维护账号可通过「编辑参数」调整布局、说明与默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
