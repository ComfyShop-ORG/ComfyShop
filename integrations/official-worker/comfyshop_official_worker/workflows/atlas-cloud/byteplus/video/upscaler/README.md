# BytePlus 视频超分

使用 BytePlus AI MediaKit 增强视频，支持场景模板、分辨率、码率、补帧与色深设置。Atlas Cloud 模型 ID 为 `byteplus/video/upscaler`。[官方模型 API](https://www.atlascloud.ai/models/byteplus/video/upscaler)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                    | 输入约定                                                               |
| ------------------ | ------------------------ | ---- | ------------------------- | ---------------------------------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `byteplus/video/upscaler` | 工作机从执行配置读取                                                   |
| `video_url`        | `video`                  | 是   | 无                        | 上传一段视频，工作机上传到 Atlas 并发送素材 URL                        |
| `tool_version`     | `tool_version`           | 否   | `standard`                | 标准 `standard` 或专业 `professional`                                  |
| `scene`            | `scene`                  | 否   | `common`                  | 标准引擎使用，选 `common`、`ugc`、`short_series`、`aigc` 或 `old_film` |
| `resolution`       | `resolution`             | 否   | `1080p`                   | 选 `240p`、`360p`、`480p`、`540p`、`720p`、`1080p`、`2k`、`4k` 或 `8k` |
| `resolution_limit` | `resolution_limit`       | 否   | 无                        | 128 至 4320 像素的短边限制，与分辨率档位二选一                         |
| `bitrate_level`    | `bitrate_level`          | 否   | `medium`                  | `low`、`medium` 或 `high`                                              |
| `fps`              | `fps`                    | 否   | 原视频帧率                | 15 至 120 fps，Atlas 建议目标不超过源帧率的 4 倍                       |
| `bit_depth`        | `bit_depth`              | 否   | 8                         | 专业引擎支持 8、10 或 12 位                                            |

在表单选择「不指定档位」后，可以填写短边像素限制。工作机会按所选引擎传递场景或位深。[官方 Schema](https://static.atlascloud.ai/model/schema/byteplus-video-upscaler.json) · [官方示例数据](https://static.atlascloud.ai/model/example/byteplus-video-upscaler.json) · [模型说明](https://static.atlascloud.ai/model/readme/byteplus-video-upscaler.md)

## API 调用

将以下示例发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "byteplus/video/upscaler",
  "video_url": "https://example.com/source.mp4",
  "tool_version": "professional",
  "resolution_limit": 2160,
  "bitrate_level": "high",
  "fps": 60,
  "bit_depth": 10
}
```

取得预测编号，按模型 Schema 用 `GET https://api.atlascloud.ai/api/v1/model/result/{id}` 轮询。收到 404 或 405 时工作机使用通用 `prediction/{id}` 续查同一任务。完成后从 `outputs` 下载成品视频。[官方调用示例](https://www.atlascloud.ai/models/byteplus/video/upscaler#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、增强引擎、场景模板和分辨率位于默认区。短边限制、码率、帧率和色深位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
