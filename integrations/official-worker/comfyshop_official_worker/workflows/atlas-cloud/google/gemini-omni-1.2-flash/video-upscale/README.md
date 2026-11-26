# Gemini Omni 1.2 Flash 视频超分

将短片提升到 720p、1080p 或 4K。Atlas Cloud 模型 ID 为 `google/gemini-omni-1.2-flash/video-upscale`。[官方模型 API](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/video-upscale)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段           | 必填 | 默认值                                       | 输入约定                                                    |
| ------------ | ------------------------ | ---- | -------------------------------------------- | ----------------------------------------------------------- |
| `model`      | `execution.config.model` | 是   | `google/gemini-omni-1.2-flash/video-upscale` | 工作机从执行配置读取                                        |
| `video`      | `video`                  | 是   | 无                                           | 上传最长 15 秒的视频，画幅 16:9 或 9:16，工作机发送素材 URL |
| `resolution` | `resolution`             | 是   | `1080p`                                      | `720p`、`1080p` 或 `4k`，须与输入档位匹配                   |
| `seed`       | `seed`                   | 否   | -1                                           | -1 为随机，也可指定整数                                     |

| 输入档位 | 可选输出    |
| -------- | ----------- |
| 360p     | 720p、1080p |
| 720p     | 1080p、4K   |
| 1080p    | 4K          |

Atlas Schema 标注 MP4，并说明保留视频帧率，建议使用 Gemini Omni 输出的 24 fps 素材。官方静态样例的输入 URL 以 `.mov` 结尾。工作机使用平台识别的视频容器类型和已知时长进行验证，分辨率组合由上游处理。[官方 Schema](https://static.atlascloud.ai/model/schema/google-gemini-omni-1.2-flash-video-upscale.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-gemini-omni-1.2-flash-video-upscale.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-gemini-omni-1.2-flash-video-upscale.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。示例输入为 720p。

```json
{
  "model": "google/gemini-omni-1.2-flash/video-upscale",
  "video": "https://example.com/clip-720p.mp4",
  "resolution": "4k",
  "seed": -1
}
```

从响应取预测编号，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `outputs` 下载超分视频。[官方调用示例](https://www.atlascloud.ai/models/google/gemini-omni-1.2-flash/video-upscale#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频与目标分辨率位于默认区，随机种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
