# Vidu Q2 Pro 图生视频

根据一张起始图和文字提示生成 1 至 10 秒的视频，支持最高 1080p。 Atlas Cloud 模型 ID 为 `vidu/q2-pro/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q2-pro/image-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                        | 必填 | 默认值                       | 输入约定                              |
| -------------------- | ------------------------------------- | ---- | ---------------------------- | ------------------------------------- |
| `model`              | `execution.config.model`              | 是   | `vidu/q2-pro/image-to-video` | 工作机从执行配置读取                  |
| `image`              | `first_frame` 或 `first_frame_source` | 是   | 无                           | 上传一张起始图，或指定公开图片 URL    |
| `prompt`             | `prompt`                              | 是   | 无                           | 描述主体、动作和镜头，最多 5,000 字符 |
| `resolution`         | `resolution`                          | 否   | `720p`                       | `540p`、`720p`、`1080p`               |
| `duration`           | `duration`                            | 否   | 5                            | 1 至 10 秒，步长为 1 秒               |
| `movement_amplitude` | `movement_amplitude`                  | 否   | `auto`                       | `auto`、`small`、`medium`、`large`    |
| `generate_audio`     | `generate_audio`                      | 否   | `true`                       | 是否生成视频音频                      |
| `bgm`                | `bgm`                                 | 否   | `false`                      | 是否添加背景音乐                      |
| `seed`               | `seed`                                | 否   | 省略                         | 整数，-1 表示随机种子                 |

工作机会先将上传图片转换为 Atlas 素材 URL。`bgm` 的模型说明写默认开启，工作流采用请求 Schema 和官方调用示例给出的 `false`。留空时省略种子。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q2-pro-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q2-pro-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q2-pro-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q2-pro-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q2-pro/image-to-video#usage-examples)

```json
{
  "model": "vidu/q2-pro/image-to-video",
  "image": "https://example.com/opening.png",
  "prompt": "长镜头掠过沙丘，风轻轻卷起沙粒，斜阳在沙脊留下影子。",
  "duration": 5,
  "resolution": "720p",
  "movement_amplitude": "auto",
  "generate_audio": true,
  "bgm": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率和成品时长位于默认区。动作幅度、音频、背景音乐、种子和图片 URL 位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
