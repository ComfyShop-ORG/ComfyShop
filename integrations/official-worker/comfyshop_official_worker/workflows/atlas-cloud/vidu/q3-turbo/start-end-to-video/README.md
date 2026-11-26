# Vidu Q3 Turbo 首尾帧生视频

用起始图和结束图生成 1 至 16 秒的过渡视频，可选 FlashVSR 超分。 Atlas Cloud 模型 ID 为 `vidu/q3-turbo/start-end-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q3-turbo/start-end-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                        | 必填 | 默认值                             | 输入约定                                                            |
| -------------------- | ------------------------------------- | ---- | ---------------------------------- | ------------------------------------------------------------------- |
| `model`              | `execution.config.model`              | 是   | `vidu/q3-turbo/start-end-to-video` | 工作机从执行配置读取                                                |
| `image`              | `first_frame` 或 `first_frame_source` | 是   | 无                                 | 上传 JPEG、PNG 或 WebP、公开图片 URL 或带媒体类型的 Base64 数据网址 |
| `end_image`          | `last_frame` 或 `last_frame_source`   | 是   | 无                                 | 上传 JPEG、PNG 或 WebP、公开图片 URL 或带媒体类型的 Base64 数据网址 |
| `prompt`             | `prompt`                              | 是   | 无                                 | 描述两张图之间的动作与过渡                                          |
| `resolution`         | `resolution`                          | 否   | `720p`                             | `540p`、`720p`、`1080p`、`1080p-sr`、`1440p-sr`                     |
| `duration`           | `duration`                            | 否   | 5                                  | 1 至 16 秒，步长为 1 秒                                             |
| `movement_amplitude` | `movement_amplitude`                  | 否   | `auto`                             | `auto`、`small`、`medium`、`large`                                  |
| `generate_audio`     | `generate_audio`                      | 否   | `true`                             | 是否生成同步音频                                                    |
| `bgm`                | `bgm`                                 | 否   | `true`                             | 是否添加背景音乐                                                    |
| `seed`               | `seed`                                | 否   | 省略                               | 整数，-1 表示随机种子                                               |

起始图的宽高比除以结束图的宽高比须在 0.8 至 1.25 之间。工作机比较上传图的尺寸，外部来源由 Atlas 检查。`1080p-sr` 由原生 720p 通过 FlashVSR 放大，`1440p-sr` 由原生 1080p 放大。Atlas 请求体上限为 20 MB，ComfyShop 每个 Base64 来源字段限制为 4 MiB。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q3-turbo-start-end-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q3-turbo-start-end-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q3-turbo-start-end-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q3-turbo-start-end-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q3-turbo/start-end-to-video#usage-examples)

```json
{
  "model": "vidu/q3-turbo/start-end-to-video",
  "image": "https://example.com/opening.png",
  "end_image": "https://example.com/ending.png",
  "prompt": "镜头绕过桌上的瓷杯，平滑过渡到结束帧里的茶水特写。",
  "resolution": "720p",
  "duration": 5,
  "movement_amplitude": "auto",
  "generate_audio": true,
  "bgm": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、结束图、提示词、分辨率和时长位于默认区。动作幅度、音频、背景音乐、种子和两帧来源位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
