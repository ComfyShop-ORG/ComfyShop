# Wan 2.7 参考生视频

用参考图、视频和可选音色引导视频中的人物、主体与场景。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.7/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.7/reference-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                                                        | 必填 | 默认值                               | 输入约定                                                                              |
| ----------------- | --------------------------------------------------------------------- | ---- | ------------------------------------ | ------------------------------------------------------------------------------------- |
| `model`           | `execution.config.model`                                              | 是   | `alibaba/wan-2.7/reference-to-video` | 工作机从执行配置读取                                                                  |
| `prompt`          | `prompt`                                                              | 是   | 无                                   | 最多 5,000 字符。用 `character1`、`character2` 等标记描述参考主体                     |
| `negative_prompt` | `negative_prompt`                                                     | 否   | 无                                   | 最多 500 字符                                                                         |
| `images`          | `reference_image_1` 至 `reference_image_5`、`reference_image_sources` | 否   | 无                                   | 至多五个公开图片 URL，每个主体一张，单张最多 20 MB                                    |
| `videos`          | `reference_video_1` 至 `reference_video_3`、`reference_video_sources` | 否   | 无                                   | 至多三个公开视频 URL。MP4 或 MOV，单段 1 至 30 秒，最多 100 MB                        |
| `audio`           | `soundtrack` 或 `soundtrack_source`                                   | 否   | 无                                   | 一份 1 至 10 秒、最多 15 MB 的 WAV 或 MP3，作为音色参考。`reference_voice` 为同义字段 |
| `resolution`      | `resolution`                                                          | 否   | `1080P`                              | 原生 `720P` 或 `1080P`。FlashVSR `1080P-SR` 或 `1440P-SR`                             |
| `ratio`           | `ratio`                                                               | 否   | `16:9`                               | `16:9`、`9:16`、`1:1`、`4:3` 或 `3:4`                                                 |
| `duration`        | `duration`                                                            | 否   | 5                                    | 2 至 10 秒的整数                                                                      |
| `prompt_extend`   | `prompt_extend`                                                       | 否   | false                                | 由模型扩写提示词                                                                      |
| `seed`            | `seed`                                                                | 否   | -1                                   | 整数范围 -1 至 2147483647。-1 使用随机种子                                            |

参考图和参考视频合计最多五份，上传文件与公开地址共同计数。参考图可用 JPEG、无透明通道的 PNG、BMP 或 WebP，宽高各 240 至 8000 像素，长短边比例最多 8:1。模型说明补充了 FlashVSR 的两个分辨率值。样例数据含有 `watermark`，当前端点参数表和请求 Schema 均使用已列出的字段，工作流按该请求定义提交。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.7-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.7-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.7-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.7-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.7/reference-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-2.7/reference-to-video",
  "prompt": "character1 在窗边的工作台摆放杯子，character2 从门口走入，镜头由门口摇向工作台。",
  "images": ["https://example.com/character-one.jpg"],
  "videos": ["https://example.com/character-two.mp4"],
  "audio": "https://example.com/voice.wav",
  "resolution": "1440P-SR",
  "ratio": "16:9",
  "duration": 8,
  "prompt_extend": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首个图片和视频槽位、分辨率、比例、时长位于默认区。其余参考素材、资料地址、音色、负面提示词、扩写和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
