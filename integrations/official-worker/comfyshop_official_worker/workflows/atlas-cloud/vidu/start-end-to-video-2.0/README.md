# Vidu 2.0 首尾帧生视频

从起始图过渡到结束图，生成 4 秒或 8 秒的视频。 Atlas Cloud 模型 ID 为 `vidu/start-end-to-video-2.0`。[官方模型 API](https://www.atlascloud.ai/models/vidu/start-end-to-video-2.0)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                                                                  | 必填 | 默认值                        | 输入约定                                                               |
| -------------------- | ------------------------------------------------------------------------------- | ---- | ----------------------------- | ---------------------------------------------------------------------- |
| `model`              | `execution.config.model`                                                        | 是   | `vidu/start-end-to-video-2.0` | 工作机从执行配置读取                                                   |
| `images`             | `first_frame` 或 `first_frame_source`，然后 `last_frame` 或 `last_frame_source` | 是   | 官方示例图                    | 正好 2 张 JPEG、PNG 或 WebP，每张最多 50 MB，宽高比大于 1:4 且小于 4:1 |
| `prompt`             | `prompt`                                                                        | 是   | 官方示例                      | 描述两张图之间的动作和过渡，最多 1,500 字符                            |
| `duration`           | `duration`                                                                      | 否   | 4                             | 4 或 8 秒                                                              |
| `movement_amplitude` | `movement_amplitude`                                                            | 否   | `auto`                        | `auto`、`small`、`medium`、`large`                                     |
| `seed`               | `seed`                                                                          | 否   | 0                             | 整数，0 表示随机种子                                                   |

每帧可上传图片，或填写公开图片 URL、带媒体类型的 Base64 数据网址。ComfyShop 依次发送起始帧和结束帧，限制每个来源字段为 4 MiB。起始图的像素总数除以结束图的像素总数须在 0.8 至 1.25 之间。工作机检查两张上传图片的像素总数比，Atlas 验证外部来源。Atlas 公布的默认示例图见请求示例。模型页面演示 `prediction` 轮询路径，静态 Schema 也列出旧的 `result` 路径。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-start-end-to-video-2.0.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-start-end-to-video-2.0.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/start-end-to-video-2.0/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/start-end-to-video-2.0#usage-examples)

```json
{
  "model": "vidu/start-end-to-video-2.0",
  "images": [
    "https://static.atlascloud.ai/media/images/1745494594983907143_liqlhd9u.jpg",
    "https://static.atlascloud.ai/media/images/1745494607637805608_31gIDzwr.jpg"
  ],
  "prompt": "镜头绕主体缓慢移动，让动作连贯地从起始画面过渡到结束画面。",
  "duration": 4,
  "movement_amplitude": "auto",
  "seed": 0
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、结束图、提示词、时长和动作幅度位于默认区。种子和两帧的外部来源位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
