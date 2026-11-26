# Seedance 2.5 草稿转正式版

使用七天内生成的 Seedance 2.5 草稿 ID 渲染正式视频。 Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5/draft-complete`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-2.5/draft-complete)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段           | 必填 | 默认值                                  | 输入约定                           |
| ------------------- | ------------------------ | ---- | --------------------------------------- | ---------------------------------- |
| `model`             | `execution.config.model` | 是   | `bytedance/seedance-2.5/draft-complete` | 工作机从执行配置读取               |
| `draft_id`          | `draft_id`               | 是   | —                                       | 已完成的 Seedance 2.5 480p 草稿 ID |
| `resolution`        | `resolution`             | 是   | `1080p`                                 | 原生 `1080p` 或 `4k`               |
| `output_format`     | `video_format`           | 否   | `mp4`                                   | `mp4` 或 `mov`。MOV 使用 YUV 4:4:4 |
| `watermark`         | `add_watermark`          | 否   | `false`                                 | 添加水印                           |
| `return_last_frame` | `include_last_frame`     | 否   | `false`                                 | 另存尾帧图片                       |

先在 Seedance 2.5 来源工作流开启草稿生成。预览完成后，从 TXT 成品复制草稿 ID。正式版继承草稿的提示词、素材、时长、比例、种子和音频设置。一个草稿可在创建后的七天内多次完成，每次都作为独立 Atlas 任务。[文生视频](../text-to-video/README.md) · [图生视频](../image-to-video/README.md) · [参考生视频](../reference-to-video/README.md)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.5-draft-complete.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-2.5-draft-complete.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-2.5-draft-complete.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-2.5/draft-complete#usage-examples)

```json
{
  "model": "bytedance/seedance-2.5/draft-complete",
  "draft_id": "<完成的草稿 ID>",
  "resolution": "1080p",
  "output_format": "mp4",
  "watermark": false,
  "return_last_frame": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的正式视频，以及开启 `return_last_frame` 时返回的尾帧图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为草稿 ID 和原生分辨率。高级参数为视频容器、水印和尾帧。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
