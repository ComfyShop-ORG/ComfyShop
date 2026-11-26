# Luma Ray 3.2 文生视频

根据提示词生成 5 秒或 10 秒视频。5 秒视频可选无缝循环或 HDR。 Atlas Cloud 模型 ID 为 `luma/ray-3.2/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/luma/ray-3.2/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填 | 默认值                       | 输入约定                                            |
| -------------- | ------------------------ | ---- | ---------------------------- | --------------------------------------------------- |
| `model`        | `execution.config.model` | 是   | `luma/ray-3.2/text-to-video` | 工作机从执行配置读取                                |
| `prompt`       | `prompt`                 | 是   | Schema 提供可编辑示例        | 描述画面和镜头运动                                  |
| `duration`     | `duration_seconds`       | 否   | `5`                          | 整数 `5` 或 `10` 秒                                 |
| `resolution`   | `resolution`             | 否   | `720p`                       | `540p`、`720p` 或 `1080p`                           |
| `aspect_ratio` | `aspect_ratio`           | 否   | `16:9`                       | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`21:9`、`9:21` |
| `loop`         | `loop`                   | 否   | `false`                      | 仅用于 5 秒、标准动态范围                           |
| `hdr`          | `hdr`                    | 否   | `false`                      | 仅用于 5 秒、720p 或 1080p，需要 HDR 权限           |

工作机在提交前校验时长、分辨率、循环和 HDR 的组合。宽高比采用 Atlas Schema 的枚举。Atlas 样例数据含 `exr_export: false`，EXR 导出需要 Atlas 发布明确的请求与返回约定。Luma 原生 API 另有 EXR 导出文档。[Luma 模型文档](https://docs.agents.lumalabs.ai/guides/model/)

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-ray-3.2-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-ray-3.2-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-ray-3.2-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/luma/ray-3.2/text-to-video#usage-examples)

```json
{
  "model": "luma/ray-3.2/text-to-video",
  "prompt": "日落照亮高山云海，镜头缓缓掠过山脊。",
  "duration": 5,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "loop": false,
  "hdr": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、时长、分辨率及宽高比。高级参数为无缝循环和 HDR。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
