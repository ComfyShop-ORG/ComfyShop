# Vidu Q2 主体参考生视频

按人物或物体分组指定参考图，生成 1 至 10 秒的视频，支持最高 1080p。 Atlas Cloud 模型 ID 为 `vidu/q2/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q2/reference-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                                            | 必填       | 默认值                       | 输入约定                                                           |
| -------------------- | --------------------------------------------------------- | ---------- | ---------------------------- | ------------------------------------------------------------------ |
| `model`              | `execution.config.model`                                  | 是         | `vidu/q2/reference-to-video` | 工作机从执行配置读取                                               |
| `subjects`           | `subject_1_id` 至 `subject_7_id` 及各主体的图片槽位和来源 | 是         | 无                           | 1 至 7 个 `{id, images}` 对象，每个主体 1 至 3 张图，合计最多 7 张 |
| `prompt`             | `prompt`                                                  | 是         | 官方示例                     | 描述主体动作和场景，以 `@主体ID` 引用主体                          |
| `duration`           | `duration`                                                | 否         | 5                            | 1 至 10 秒，步长为 1 秒                                            |
| `resolution`         | `resolution`                                              | 否         | `720p`                       | `540p`、`720p`、`1080p`                                            |
| `aspect_ratio`       | `aspect_ratio`                                            | 否         | `16:9`                       | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`                                |
| `movement_amplitude` | `movement_amplitude`                                      | 否         | `auto`                       | `auto`、`small`、`medium`、`large`                                 |
| `generate_audio`     | `generate_audio`                                          | 否         | `true`                       | 是否生成音频                                                       |
| `audio_type`         | `audio_type`                                              | 生成音频时 | `all`                        | `all`、`speech_only`、`sound_effect_only`                          |
| `seed`               | `seed`                                                    | 否         | 0                            | 整数，-1 表示随机种子                                              |

每个主体填写 ID 与至少一张图。支持上传 JPEG、PNG 或 WebP，或逐行填写公开 URL 和带媒体类型的 Base64 数据网址。图像每边至少 128 像素，宽高比大于 1:4 且小于 4:1。工作机先按槽位顺序组织已上传的图片，再追加该主体的来源。Atlas 请求体上限为 20 MB，ComfyShop 每个来源字段限制为 4 MiB。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q2-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q2-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q2-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q2-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q2/reference-to-video#usage-examples)

```json
{
  "model": "vidu/q2/reference-to-video",
  "subjects": [
    {
      "id": "hiker",
      "images": ["https://example.com/hiker-front.png", "https://example.com/hiker-side.png"]
    }
  ],
  "prompt": "镜头从侧面跟拍 @hiker 沿湖边小径行走。",
  "resolution": "720p",
  "duration": 5,
  "aspect_ratio": "16:9",
  "movement_amplitude": "auto",
  "generate_audio": true,
  "audio_type": "all",
  "seed": 0
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首个主体的 ID 与第一张图、画面比例、分辨率及成品时长位于默认区。更多主体、每组来源、动作幅度、音频和种子位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
