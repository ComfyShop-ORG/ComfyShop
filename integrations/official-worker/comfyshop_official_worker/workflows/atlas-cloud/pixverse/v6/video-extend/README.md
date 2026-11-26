# PixVerse V6 视频延长

根据提示词续接原视频，生成 1 至 15 秒的新内容。 Atlas Cloud 模型 ID 为 `pixverse/v6/video-extend`。[官方模型 API](https://www.atlascloud.ai/models/pixverse/v6/video-extend)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段                       | 必填 | 默认值                     | 输入约定                               |
| ---------- | ------------------------------------ | ---- | -------------------------- | -------------------------------------- |
| `model`    | `execution.config.model`             | 是   | `pixverse/v6/video-extend` | 工作机从执行配置读取                   |
| `video`    | `source_video` 或 `source_video_url` | 是   | —                          | MP4、MOV、WebM，上传或提供公开视频 URL |
| `prompt`   | `prompt`                             | 是   | —                          | 续写动作和场景，1 至 5,000 字符        |
| `duration` | `duration_seconds`                   | 是   | `5`                        | 续接时长，整数 1 至 15 秒              |
| `quality`  | `resolution`                         | 是   | `720p`                     | `360p`、`540p`、`720p`、`1080p`        |
| `seed`     | `seed`                               | 否   | 由 Atlas 选取              | 整数，留空时省略参数                   |

续接时长独立于原视频长度。工作机上传视频后使用 Atlas 返回的地址发起生成。填写 URL 时，原视频需要可公开访问。

[官方 Schema](https://static.atlascloud.ai/model/schema/pixverse-v6-video-extend.json) · [官方示例数据](https://static.atlascloud.ai/model/example/pixverse-v6-video-extend.json) · [模型说明](https://static.atlascloud.ai/model/readme/pixverse-v6-video-extend.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/pixverse/v6-video-extend/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/pixverse/v6/video-extend#usage-examples)

```json
{
  "model": "pixverse/v6/video-extend",
  "video": "https://example.com/source.mp4",
  "prompt": "镜头继续后退，逐渐露出整个海岸。",
  "duration": 5,
  "quality": "720p"
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为原视频、提示词、续接时长和分辨率。高级参数为原视频 URL 与随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
