# Veo 3.1 图生视频

用提示词让起始图动起来，可添加结束图，可设置最高 4K 分辨率。 Atlas Cloud 模型 ID 为 `google/veo3.1/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/google/veo3.1/image-to-video)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                        | 必填 | 默认值                         | 输入约定                                |
| ----------------- | ------------------------------------- | ---- | ------------------------------ | --------------------------------------- |
| `model`           | `execution.config.model`              | 是   | `google/veo3.1/image-to-video` | 工作机从执行配置读取                    |
| `prompt`          | `prompt`                              | 是   | 无                             | 描述主体、场景及镜头                    |
| `image`           | `first_frame` 或 `first_frame_source` | 是   | 无                             | 上传起始图或填写公开图片 URL            |
| `last_image`      | `last_frame` 或 `last_frame_source`   | 否   | 无                             | 上传结束图或填写公开图片 URL            |
| `aspect_ratio`    | `aspect_ratio`                        | 否   | `16:9`                         | `16:9` 或 `9:16`                        |
| `duration`        | `duration`                            | 否   | 8                              | `4`、`6` 或 `8` 秒。1080p 和 4K 限 8 秒 |
| `resolution`      | `resolution`                          | 否   | `720p`                         | `720p`、`1080p` 或 `4k`                 |
| `generate_audio`  | `generate_audio`                      | 否   | false                          | 同时生成音频                            |
| `negative_prompt` | `negative_prompt`                     | 否   | 无                             | 描述应避开的画面元素，留空时省略        |
| `seed`            | `seed`                                | 否   | 由 Atlas 选择                  | 整数，留空时省略                        |

工作机将上传图转换成素材地址，按分辨率校验时长，并按官方调用示例轮询 `prediction/{id}`。静态 Schema 的旧路径为 `result/{id}`。端点参数表与 Schema 支持 `4k`，静态模型介绍中的分辨率上限为 1080p。[官方 Schema](https://static.atlascloud.ai/model/schema/google-veo3.1-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-veo3.1-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-veo3.1-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/en/more-models/google/veo3.1-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/google/veo3.1/image-to-video#usage-examples)

```json
{
  "model": "google/veo3.1/image-to-video",
  "prompt": "镜头缓缓靠近玻璃花瓶，花瓣随风向上飘，最后停在结束图的画面。",
  "image": "https://example.com/petals-start.jpg",
  "last_image": "https://example.com/petals-end.jpg",
  "aspect_ratio": "16:9",
  "resolution": "4k",
  "duration": 8,
  "generate_audio": true,
  "negative_prompt": "画面闪烁，过曝的窗户"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首尾图片、比例、分辨率和时长位于默认区。图片地址、音频开关、负面提示词与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
