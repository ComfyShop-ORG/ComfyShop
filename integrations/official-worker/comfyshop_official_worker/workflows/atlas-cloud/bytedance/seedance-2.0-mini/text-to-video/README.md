# Seedance 2.0 Mini 文生视频

用提示词生成 4 至 15 秒的视频，可同时生成音频和导出尾帧。 Atlas Cloud 模型 ID 为 `bytedance/seedance-2.0-mini/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-2.0-mini/text-to-video)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段           | 必填 | 默认值                                      | 输入约定                                                       |
| ------------------- | ------------------------ | ---- | ------------------------------------------- | -------------------------------------------------------------- |
| `model`             | `execution.config.model` | 是   | `bytedance/seedance-2.0-mini/text-to-video` | 工作机从执行配置读取                                           |
| `prompt`            | `prompt`                 | 是   | 官方可编辑示例                              | 建议中文少于 500 字或英文少于 1,000 词                         |
| `duration`          | `duration_seconds`       | 否   | `5`                                         | 整数 4 至 15 或 `-1` 自动                                      |
| `ratio`             | `aspect_ratio`           | 否   | `adaptive`                                  | `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9` 或根据提示词自适应 |
| `resolution`        | `resolution`             | 否   | `720p`                                      | `480p`、`720p`、`720p-SR`、`1080p-SR`、`1440p-SR`              |
| `bitrate_mode`      | `bitrate_mode`           | 否   | `standard`                                  | `standard` 或 `high`。高码率增大文件，Token 计费相同           |
| `generate_audio`    | `generate_audio`         | 否   | `true`                                      | 生成同步音频                                                   |
| `seed`              | `seed`                   | 否   | `-1`                                        | 整数 `-1` 至 `4294967295`，`-1` 随机                           |
| `watermark`         | `add_watermark`          | 否   | `false`                                     | 添加水印                                                       |
| `return_last_frame` | `include_last_frame`     | 否   | `false`                                     | 另存尾帧图片                                                   |

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.0-mini-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-2.0-mini-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-2.0-mini-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-2.0-mini-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-2.0-mini/text-to-video#usage-examples)

```json
{
  "model": "bytedance/seedance-2.0-mini/text-to-video",
  "prompt": "A golden retriever running on a sunny beach, waves crashing in the background, cinematic lighting",
  "duration": 5,
  "ratio": "adaptive",
  "resolution": "720p",
  "bitrate_mode": "standard",
  "generate_audio": true,
  "seed": -1,
  "watermark": false,
  "return_last_frame": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的视频，以及开启 `return_last_frame` 后返回的尾帧图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、画面比例和分辨率。高级参数为码率、音频、种子、水印和尾帧。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
