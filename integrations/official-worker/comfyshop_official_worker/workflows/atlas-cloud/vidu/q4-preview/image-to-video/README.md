# Vidu Q4 Preview 图生视频

用一张起始图生成 3 至 16 秒的视频，可选 4K、同步音频和提示词扩写。 Atlas Cloud 模型 ID 为 `vidu/q4-preview/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q4-preview/image-to-video)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                        | 必填 | 默认值                           | 输入约定                            |
| ------------------------- | ------------------------------------- | ---- | -------------------------------- | ----------------------------------- |
| `model`                   | `execution.config.model`              | 是   | `vidu/q4-preview/image-to-video` | 工作机从执行配置读取                |
| `image`                   | `first_frame` 或 `first_frame_source` | 是   | 无                               | 一张 JPEG、PNG 或 WebP，最多 50 MB  |
| `prompt`                  | `prompt`                              | 否   | 官方示例                         | 最多 20,000 字符，留空时省略        |
| `duration`                | `duration`                            | 否   | 5                                | 3 至 16 秒的整数                    |
| `resolution`              | `resolution`                          | 否   | `720p`                           | `540p`、`720p`、`1080p`、`2k`、`4k` |
| `generate_audio`          | `generate_audio`                      | 否   | `true`                           | 是否生成同步对白、音效和环境声      |
| `enable_prompt_expansion` | `enable_prompt_expansion`             | 否   | `false`                          | 生成前改写并丰富提示词              |
| `seed`                    | `seed`                                | 否   | -1                               | 整数，-1 使用随机种子               |

起始图支持上传、公开 URL 或带媒体类型的 Base64 数据网址。ComfyShop 的来源字段限制为 4 MiB。工作流字段依据当前请求 Schema，静态示例数据还包含 `watermark`。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q4-preview-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q4-preview-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q4-preview-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/vidu/q4-preview/image-to-video#usage-examples)

```json
{
  "model": "vidu/q4-preview/image-to-video",
  "image": "https://example.com/opening.png",
  "prompt": "镜头从窗边转向书桌，白色窗帘随风摆动。",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": true,
  "enable_prompt_expansion": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率和时长位于默认区。种子、同步音频、扩写和图片来源位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
