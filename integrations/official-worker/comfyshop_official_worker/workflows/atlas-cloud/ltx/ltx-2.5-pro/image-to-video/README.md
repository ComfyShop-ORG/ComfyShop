# LTX 2.5 Pro 图生视频

从首帧图片生成最高 4K 的视频，可指定尾帧并生成同步音频。 Atlas Cloud 模型 ID 为 `ltx/ltx-2.5-pro/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/ltx/ltx-2.5-pro/image-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                        | 必填 | 默认值                           | 输入约定                                                                                            |
| ---------------- | ------------------------------------- | ---- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| `model`          | `execution.config.model`              | 是   | `ltx/ltx-2.5-pro/image-to-video` | 工作机从执行配置读取                                                                                |
| `image`          | `first_frame` 或 `first_frame_source` | 是   | —                                | 首帧，上传、URL、Base64 或 `asset://`                                                               |
| `last_image`     | `last_frame` 或 `last_frame_source`   | 否   | —                                | 尾帧，上传、URL、Base64 或 `asset://`                                                               |
| `prompt`         | `prompt`                              | 否   | Schema 提供可编辑示例            | 描述场景、主体动作、镜头运动和氛围                                                                  |
| `duration`       | `duration_seconds`                    | 否   | `-1`                             | `-1` 自动，或 `6`、`8`、`10` 秒                                                                     |
| `resolution`     | `resolution`                          | 否   | `720p`                           | `720p`、`1080p`、`1440p`、`4k`                                                                      |
| `aspect_ratio`   | `aspect_ratio`                        | 否   | `16:9`                           | `16:9` 横向或 `9:16` 竖向                                                                           |
| `fps`            | `fps`                                 | 否   | `24`                             | `24` 或 `48`                                                                                        |
| `generate_audio` | `generate_audio`                      | 否   | `true`                           | 生成环境音、音效或语音                                                                              |
| `camera_motion`  | `camera_motion`                       | 否   | —                                | `dolly_in`、`dolly_out`、`dolly_left`、`dolly_right`、`jib_up`、`jib_down`、`static`、`focus_shift` |

手动时长可选 6、8 或 10 秒。选择 `-1` 时由模型确定时长。首尾帧支持 JPEG、PNG、WebP。较大的图片可直接上传。[LTX 原生输入格式](https://docs.ltx.io/input-formats/#images)

[官方 Schema](https://static.atlascloud.ai/model/schema/ltx-ltx-2.5-pro-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/ltx-ltx-2.5-pro-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/ltx-ltx-2.5-pro-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/ltx/ltx-2.5-pro/image-to-video#usage-examples)

```json
{
  "model": "ltx/ltx-2.5-pro/image-to-video",
  "image": "https://example.com/first.png",
  "last_image": "https://example.com/last.png",
  "prompt": "黄昏的云海中，一只鹰从镜头前掠过。",
  "duration": 10,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "fps": 48,
  "generate_audio": true,
  "camera_motion": "dolly_in"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首帧、可选尾帧、提示词、时长、分辨率和宽高比。高级参数为帧率、同步音频、镜头运动及图片来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
