# PixVerse V6 文生视频

根据文字生成 1 至 15 秒的视频，可生成随画面同步的音频。 Atlas Cloud 模型 ID 为 `pixverse/v6/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/pixverse/v6/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                      | 输入约定                                                  |
| -------------- | ------------------------ | ---- | --------------------------- | --------------------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `pixverse/v6/text-to-video` | 工作机从执行配置读取                                      |
| `prompt`       | `prompt`                 | 是   | —                           | 非空文字，1 至 5,000 字符                                 |
| `duration`     | `duration_seconds`       | 否   | `5`                         | 整数 1 至 15 秒                                           |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                      | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`2:3`、`3:2`、`21:9` |
| `quality`      | `resolution`             | 否   | `720p`                      | `360p`、`540p`、`720p`、`1080p`                           |
| `sound`        | `generate_audio`         | 否   | `true`                      | 生成同步音频，使用 Atlas 的有声档位计费                   |
| `seed`         | `seed`                   | 否   | 由 Atlas 选取               | 整数，留空时省略参数                                      |

请在提示词中说明场景和运动方式。

[官方 Schema](https://static.atlascloud.ai/model/schema/pixverse-v6-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/pixverse-v6-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/pixverse-v6-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/pixverse/v6-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/pixverse/v6/text-to-video#usage-examples)

```json
{
  "model": "pixverse/v6/text-to-video",
  "prompt": "晨光掠过云层，镜头沿山脊缓缓前移。",
  "duration": 5,
  "aspect_ratio": "16:9",
  "quality": "720p",
  "sound": true
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、宽高比和分辨率。高级参数为同步音频和随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
