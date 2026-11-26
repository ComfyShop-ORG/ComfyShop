# 腾讯云视频超分

使用腾讯云 MPS 增强已有视频。Atlas Cloud 模型 ID 为 `tencent/video/upscaler`。[官方模型 API](https://www.atlascloud.ai/models/tencent/video/upscaler)

## Atlas 接口参数

| Atlas 参数      | ComfyShop 字段           | 必填 | 默认值                   | 输入约定                                                           |
| --------------- | ------------------------ | ---- | ------------------------ | ------------------------------------------------------------------ |
| `model`         | `execution.config.model` | 是   | `tencent/video/upscaler` | 工作机从执行配置读取                                               |
| `video_url`     | `video`                  | 是   | 无                       | 上传一段视频，工作机上传到 Atlas 并发送素材 URL                    |
| `template`      | `template`               | 否   | `anime-enhance-4k`       | 表单提供 Atlas Schema 中的 24 个模板                               |
| `short`         | `short`                  | 否   | 0                        | 0 保留源分辨率，正整数按所选模板档位校验。留空时使用服务端模板尺寸 |
| `fps`           | `fps`                    | 否   | 原帧率                   | 指定大于等于 1 的整数作为补帧目标                                  |
| `keep_metadata` | `keep_metadata`          | 否   | true                     | 保留源视频媒体元数据                                               |

模板包括实拍增强、动漫增强、老片修复、实拍远景小脸优化、动漫远景小脸优化与 Seedance 2 增强。每组有 720p、1080p、2K 和 4K。

| 模板档位 | 输出短边像素 |
| -------- | ------------ |
| 720p     | 1 至 720     |
| 1080p    | 721 至 1080  |
| 2K       | 1081 至 1440 |
| 4K       | 1441 至 2160 |

模型说明要求选择模板，表单默认选择 `anime-enhance-4k`。静态示例用 `anime-enhance-2k` 配 `short: 2160`。当前 Schema 的 2K 档位上限为 1440，工作机按此范围校验，并接受 Schema 的特殊值 0。[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-video-upscaler.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-video-upscaler.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-video-upscaler.md)

## API 调用

将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "tencent/video/upscaler",
  "video_url": "https://example.com/source.mp4",
  "template": "anime-enhance-2k",
  "short": 1440,
  "keep_metadata": true
}
```

从响应取预测编号，按 Schema 通过 `GET https://api.atlascloud.ai/api/v1/model/result/{id}` 查询状态。收到 404 或 405 时工作机使用通用 `prediction/{id}` 续查，完成后下载 `outputs` 中的视频。[官方调用示例](https://www.atlascloud.ai/models/tencent/video/upscaler#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

视频与增强模板位于默认区。输出短边、目标帧率和元数据开关位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
