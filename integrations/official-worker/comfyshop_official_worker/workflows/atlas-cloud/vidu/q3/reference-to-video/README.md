# Vidu Q3 参考生视频

使用一至四张参考图生成 3 至 16 秒的视频，可选 FlashVSR 超分。 Atlas Cloud 模型 ID 为 `vidu/q3/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q3/reference-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                                              | 必填 | 默认值                       | 输入约定                                                                                  |
| -------------------- | ----------------------------------------------------------- | ---- | ---------------------------- | ----------------------------------------------------------------------------------------- |
| `model`              | `execution.config.model`                                    | 是   | `vidu/q3/reference-to-video` | 工作机从执行配置读取                                                                      |
| `images`             | `reference_image_1` 至 `reference_image_4`、`image_sources` | 是   | 官方示例图                   | 1 至 4 张 JPEG、PNG 或 WebP，每张最多 50 MB，每边至少 128 像素，宽高比大于 1:4 且小于 4:1 |
| `prompt`             | `prompt`                                                    | 是   | 官方示例                     | 描述主体动作、场景和镜头                                                                  |
| `duration`           | `duration`                                                  | 否   | 5                            | 3 至 16 秒，步长为 1 秒                                                                   |
| `resolution`         | `resolution`                                                | 否   | `720p`                       | `540p`、`720p`、`1080p`、`1080p-sr`、`1440p-sr`                                           |
| `generate_audio`     | `generate_audio`                                            | 否   | `true`                       | 是否生成视频音频                                                                          |
| `aspect_ratio`       | `aspect_ratio`                                              | 否   | `16:9`                       | `16:9`、`9:16`、`3:4`、`4:3`、`1:1`                                                       |
| `movement_amplitude` | `movement_amplitude`                                        | 否   | `auto`                       | `auto`、`small`、`medium`、`large`                                                        |
| `seed`               | `seed`                                                      | 否   | 0                            | 整数，-1 表示随机种子                                                                     |

图片可上传，也可逐行填写公开 URL 或带媒体类型的 Base64 数据网址。上传图按栏位排序，外部图随后追加。ComfyShop 的来源字段限制为 4 MiB。Atlas 公布的默认示例图见请求示例。`1080p-sr` 由原生 720p 通过 FlashVSR 放大，`1440p-sr` 由原生 1080p 放大。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q3-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q3-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q3-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q3-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q3/reference-to-video#usage-examples)

```json
{
  "model": "vidu/q3/reference-to-video",
  "images": [
    "https://static.atlascloud.ai/media/images/1745492230971199265_J3J5tO7p.jpg",
    "https://static.atlascloud.ai/media/images/1745492247387641003_Z3jDAxur.jpg"
  ],
  "prompt": "镜头沿着湖边小径前移，画面中的人物走过树下。",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": true,
  "aspect_ratio": "16:9",
  "movement_amplitude": "auto",
  "seed": 0
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

首张参考图、提示词、画面比例、分辨率、时长和动作幅度位于默认区。其余参考图、来源、生成音频和种子位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
