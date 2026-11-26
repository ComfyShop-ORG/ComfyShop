# Luma Ray 3.2 图生视频

用首帧和可选尾帧生成 5 秒或 10 秒视频，画面比例随首帧。 Atlas Cloud 模型 ID 为 `luma/ray-3.2/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/luma/ray-3.2/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                        | 必填 | 默认值                        | 输入约定                                   |
| ------------ | ------------------------------------- | ---- | ----------------------------- | ------------------------------------------ |
| `model`      | `execution.config.model`              | 是   | `luma/ray-3.2/image-to-video` | 工作机从执行配置读取                       |
| `image`      | `first_frame` 或 `first_frame_source` | 是   | —                             | 首帧，上传、公开 URL、Base64 或 `asset://` |
| `last_image` | `last_frame` 或 `last_frame_source`   | 否   | —                             | 可选尾帧，接受同样的来源                   |
| `prompt`     | `prompt`                              | 否   | Schema 提供可编辑示例         | 描述画面和镜头运动                         |
| `duration`   | `duration_seconds`                    | 否   | `5`                           | 整数 `5` 或 `10` 秒                        |
| `resolution` | `resolution`                          | 否   | `720p`                        | `540p`、`720p` 或 `1080p`                  |
| `loop`       | `loop`                                | 否   | `false`                       | 仅用于 5 秒、标准动态范围                  |
| `hdr`        | `hdr`                                 | 否   | `false`                       | 仅用于 5 秒、720p 或 1080p，需要 HDR 权限  |

工作机在提交前校验时长、分辨率、循环和 HDR 的组合。输出宽高比由首帧决定。首尾帧支持 JPEG、PNG、WebP 或静态 GIF。[Luma 素材格式](https://docs.agents.lumalabs.ai/guides/faq/)

Atlas 样例数据含 `exr_export: false`，EXR 导出需要 Atlas 发布明确的请求与返回约定。Luma 原生 API 另有 EXR 导出文档。[Luma 模型文档](https://docs.agents.lumalabs.ai/guides/model/)

[官方 Schema](https://static.atlascloud.ai/model/schema/luma-ray-3.2-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/luma-ray-3.2-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/luma-ray-3.2-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/luma/ray-3.2/image-to-video#usage-examples)

```json
{
  "model": "luma/ray-3.2/image-to-video",
  "image": "https://example.com/first.png",
  "last_image": "https://example.com/last.png",
  "prompt": "日落照亮高山云海，镜头缓缓掠过山脊。",
  "duration": 5,
  "resolution": "720p",
  "loop": false,
  "hdr": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首帧、可选尾帧、提示词、时长和分辨率。高级参数为无缝循环、HDR 以及首尾帧来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
