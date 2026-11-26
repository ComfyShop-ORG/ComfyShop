# Veo 3.1 Fast 文生视频

依据提示词生成视频，可设置最高 4K 分辨率、时长与音频。 Atlas Cloud 模型 ID 为 `google/veo3.1-fast/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/veo3.1-fast/text-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段           | 必填 | 默认值                             | 输入约定                                |
| ----------------- | ------------------------ | ---- | ---------------------------------- | --------------------------------------- |
| `model`           | `execution.config.model` | 是   | `google/veo3.1-fast/text-to-video` | 工作机从执行配置读取                    |
| `prompt`          | `prompt`                 | 是   | 无                                 | 描述主体、场景及镜头                    |
| `aspect_ratio`    | `aspect_ratio`           | 否   | `16:9`                             | `16:9` 或 `9:16`                        |
| `duration`        | `duration`               | 否   | 8                                  | `4`、`6` 或 `8` 秒。1080p 和 4K 限 8 秒 |
| `resolution`      | `resolution`             | 否   | `720p`                             | `720p`、`1080p` 或 `4k`                 |
| `generate_audio`  | `generate_audio`         | 否   | false                              | 同时生成音频                            |
| `negative_prompt` | `negative_prompt`        | 否   | 无                                 | 描述应避开的画面元素，留空时省略        |
| `seed`            | `seed`                   | 否   | 由 Atlas 选择                      | 整数，留空时省略                        |

工作机按分辨率校验时长，并按官方调用示例轮询 `prediction/{id}`。静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/google-veo3.1-fast-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-veo3.1-fast-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-veo3.1-fast-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/google/veo3.1-fast/text-to-video#usage-examples)

```json
{
  "model": "google/veo3.1-fast/text-to-video",
  "prompt": "广角镜头跟随山间列车缓缓驶过白桦林，清晨阳光照亮车窗。",
  "aspect_ratio": "16:9",
  "resolution": "4k",
  "duration": 8,
  "generate_audio": true,
  "negative_prompt": "模糊的车窗，过曝的天空"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、比例、分辨率和时长位于默认区。音频开关、负面提示词和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
