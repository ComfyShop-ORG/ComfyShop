# MiniMax H3 Fast 图生视频

用提示词生成 480P 视频。可上传首帧和尾帧控制镜头起点与结尾。Atlas Cloud 模型 ID 为 `minimax/h3-fast/image-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-fast/image-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                           | 输入约定               |
| ------------------ | ------------------------ | ---- | -------------------------------- | ---------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-fast/image-to-video` | 工作机从执行配置读取   |
| `prompt`           | `prompt`                 | 是   | 由用户填写                       | 描述画面动作或运镜     |
| `image`            | `first_frame`            | 否   | 由用户上传                       | 起始图片               |
| `end_image`        | `last_frame`             | 否   | 由用户上传                       | 结束图片               |
| `duration`         | `duration_seconds`       | 是   | `8`                              | 5 至 15 秒的整数       |
| `resolution`       | `resolution`             | 是   | `480P`                           | 唯一枚举为 `480P`      |
| `ratio`            | `aspect_ratio`           | 否   | `adaptive`                       | 唯一枚举为 `adaptive`  |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                          | 是否在生成前扩写提示词 |

首尾帧支持 PNG、JPEG 和 WebP。工作机先上传已提供的帧，再把返回的 URL 写入对应请求字段。空槽会省略。直接调用 Atlas API 可传公开 URL 或 Base64。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-fast-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-fast-image-to-video.json) · [素材上传](https://www.atlascloud.ai/docs/upload-files)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。图片地址为示例。

```json
{
  "model": "minimax/h3-fast/image-to-video",
  "prompt": "夕阳渐暗，镜头缓慢拉远，最后对准亮起的路灯。",
  "image": "https://example.com/opening.png",
  "end_image": "https://example.com/ending.png",
  "duration": 8,
  "resolution": "480P",
  "ratio": "adaptive",
  "prompt_expansion": false
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 获取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-fast/image-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

首尾帧、提示词和时长位于默认区，扩写位于高级区，固定分辨率与自适应比例位于隐藏区。维护账号可通过「编辑参数」调整布局与说明。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
