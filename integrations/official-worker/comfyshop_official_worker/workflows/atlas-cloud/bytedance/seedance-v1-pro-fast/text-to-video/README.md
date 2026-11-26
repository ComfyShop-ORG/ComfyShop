# Seedance v1 Pro Fast 文生视频

根据文字生成 2 至 12 秒的视频，可选 480p、720p 或 1080p。 Atlas Cloud 模型 ID 为 `bytedance/seedance-v1-pro-fast/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-v1-pro-fast/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                                         | 输入约定                                    |
| -------------- | ------------------------ | ---- | ---------------------------------------------- | ------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `bytedance/seedance-v1-pro-fast/text-to-video` | 工作机从执行配置读取                        |
| `prompt`       | `prompt`                 | 是   | 无                                             | 描述主体、场景和镜头，最多 2,000 字符       |
| `resolution`   | `resolution`             | 否   | `480p`                                         | `480p`、`720p`、`1080p`                     |
| `duration`     | `duration`               | 否   | 5                                              | 2 至 12 秒的整数                            |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                                         | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `camera_fixed` | `camera_fixed`           | 否   | `false`                                        | 是否固定摄像机位置                          |
| `seed`         | `seed`                   | 否   | -1                                             | 整数，-1 使用随机种子                       |

静态 Schema 列有旧的 `result` 路径，当前模型 API 示例使用 `prediction` 轮询。 [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-v1-pro-fast-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-v1-pro-fast-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-v1-pro-fast-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-v1-pro-fast-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-v1-pro-fast/text-to-video#usage-examples)

```json
{
  "model": "bytedance/seedance-v1-pro-fast/text-to-video",
  "prompt": "镜头绕过一辆行进中的列车，远处的高架桥掠过画面。",
  "resolution": "480p",
  "duration": 5,
  "aspect_ratio": "16:9",
  "camera_fixed": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、分辨率、画面比例和成品时长位于默认区。固定镜头与种子位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
