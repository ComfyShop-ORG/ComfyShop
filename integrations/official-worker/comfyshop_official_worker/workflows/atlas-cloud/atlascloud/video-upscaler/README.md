# Atlas Cloud 视频放大

将一段视频提升到 1080p 或 2K。Atlas Cloud 模型 ID 为 `atlascloud/video-upscaler`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/video-upscaler)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段           | 必填 | 默认值                      | 输入约定                                        |
| ------------------- | ------------------------ | ---- | --------------------------- | ----------------------------------------------- |
| `model`             | `execution.config.model` | 是   | `atlascloud/video-upscaler` | 工作机从执行配置读取                            |
| `video`             | `video`                  | 是   | 无                          | 上传一段视频，工作机上传到 Atlas 并发送素材 URL |
| `target_resolution` | `target_resolution`      | 否   | `1080p`                     | `1080p` 或 `2k`                                 |

| 目标分辨率             | 输入时长上限 | 输入帧数上限 |
| ---------------------- | ------------ | ------------ |
| `1080p`                | 53 秒        | 1590 帧      |
| `2k`（2560×1440 档位） | 23 秒        | 690 帧       |

输入最高 30 fps。Atlas 在计费和处理前探测时长、帧率及总帧数。任务会按所选档位校验全部限制。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-video-upscaler.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-video-upscaler.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-video-upscaler.md)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "atlascloud/video-upscaler",
  "video": "https://example.com/source-clip.mp4",
  "target_resolution": "2k"
}
```

用预测编号轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成后从 `outputs` 下载视频原件。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/video-upscaler#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频与目标分辨率位于默认区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
