# Vidu 2.0 图生视频

根据一张起始图和文字提示生成 4 秒或 8 秒的视频。 Atlas Cloud 模型 ID 为 `vidu/image-to-video-2.0`。[官方模型 API](https://www.atlascloud.ai/models/vidu/image-to-video-2.0)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                        | 必填 | 默认值                    | 输入约定                                                      |
| -------------------- | ------------------------------------- | ---- | ------------------------- | ------------------------------------------------------------- |
| `model`              | `execution.config.model`              | 是   | `vidu/image-to-video-2.0` | 工作机从执行配置读取                                          |
| `image`              | `first_frame` 或 `first_frame_source` | 是   | 官方示例图                | 1 张 JPEG、PNG 或 WebP，最多 50 MB，宽高比大于 1:4 且小于 4:1 |
| `prompt`             | `prompt`                              | 是   | 官方示例                  | 最多 1,500 字符                                               |
| `duration`           | `duration`                            | 否   | 4                         | 4 或 8 秒                                                     |
| `movement_amplitude` | `movement_amplitude`                  | 否   | `auto`                    | `auto`、`small`、`medium`、`large`                            |
| `seed`               | `seed`                                | 否   | 0                         | 整数，0 表示随机种子                                          |

起始图支持上传、公开 URL 或带媒体类型的 Base64 数据网址。ComfyShop 的来源字段限制为 4 MiB，上传可提交更大的图片。Atlas 公布的默认示例图见请求示例，可将该地址填入高级区。模型页面演示 `prediction` 轮询路径，静态 Schema 也列出旧的 `result` 路径。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-image-to-video-2.0.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-image-to-video-2.0.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/image-to-video-2.0/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/image-to-video-2.0#usage-examples)

```json
{
  "model": "vidu/image-to-video-2.0",
  "image": "https://static.atlascloud.ai/media/images/1745492812795806468_P4jFBxup.jpg",
  "prompt": "镜头沿街市平移，跟随画面中的人物转身和起舞。",
  "duration": 4,
  "movement_amplitude": "auto",
  "seed": 0
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、时长和动作幅度位于默认区。种子和起始图来源位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
