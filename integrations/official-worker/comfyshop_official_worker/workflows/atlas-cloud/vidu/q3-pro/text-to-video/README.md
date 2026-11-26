# Vidu Q3 Pro 文生视频

根据文字生成 1 至 16 秒的视频，可选通用或动画风格及 FlashVSR 超分。 Atlas Cloud 模型 ID 为 `vidu/q3-pro/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q3-pro/text-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段           | 必填 | 默认值                      | 输入约定                                        |
| -------------------- | ------------------------ | ---- | --------------------------- | ----------------------------------------------- |
| `model`              | `execution.config.model` | 是   | `vidu/q3-pro/text-to-video` | 工作机从执行配置读取                            |
| `prompt`             | `prompt`                 | 是   | 无                          | 描述视频的主体、场景、动作和镜头                |
| `style`              | `style`                  | 否   | `general`                   | `general` 或 `anime`                            |
| `resolution`         | `resolution`             | 否   | `720p`                      | `540p`、`720p`、`1080p`、`1080p-sr`、`1440p-sr` |
| `duration`           | `duration`               | 否   | 5                           | 1 至 16 秒，步长为 1 秒                         |
| `aspect_ratio`       | `aspect_ratio`           | 否   | `4:3`                       | `16:9`、`9:16`、`4:3`、`3:4`、`1:1`             |
| `movement_amplitude` | `movement_amplitude`     | 否   | `auto`                      | `auto`、`small`、`medium`、`large`              |
| `seed`               | `seed`                   | 否   | 省略                        | 整数，-1 表示随机种子                           |
| `generate_audio`     | `generate_audio`         | 否   | `true`                      | 是否生成视频音频                                |
| `bgm`                | `bgm`                    | 否   | `true`                      | 是否添加背景音乐                                |

`1080p-sr` 先生成原生 720p 再通过 FlashVSR 放大，`1440p-sr` 从原生 1080p 放大。留空时省略种子。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q3-pro-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q3-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q3-pro-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q3-pro-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q3-pro/text-to-video#usage-examples)

```json
{
  "model": "vidu/q3-pro/text-to-video",
  "prompt": "低角度跟拍骑行者经过雨后的街道，路灯在地面映出暖色倒影。",
  "style": "general",
  "resolution": "720p",
  "duration": 5,
  "aspect_ratio": "4:3",
  "movement_amplitude": "auto",
  "generate_audio": true,
  "bgm": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、风格、画面比例、分辨率和时长位于默认区。动作幅度、音频、背景音乐和种子位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
