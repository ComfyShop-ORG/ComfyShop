# Seedance 2.5 图生视频

从起始图生成视频，可指定结束图或生成 480p 草稿。 Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedance-2.5/image-to-video)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                        | 必填 | 默认值                                  | 输入约定                                                                                                                              |
| ------------------- | ------------------------------------- | ---- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `model`             | `execution.config.model`              | 是   | `bytedance/seedance-2.5/image-to-video` | 工作机从执行配置读取                                                                                                                  |
| `image`             | `first_frame` 或 `first_frame_source` | 是   | —                                       | 起始帧图片                                                                                                                            |
| `last_image`        | `last_frame` 或 `last_frame_source`   | 否   | —                                       | 结束帧图片                                                                                                                            |
| `prompt`            | `prompt`                              | 否   | 官方可编辑示例                          | 描述动作或镜头，可留空                                                                                                                |
| `duration`          | `duration_seconds`                    | 否   | `5`                                     | 整数 4 至 30 或 `-1` 自动                                                                                                             |
| `resolution`        | `resolution`                          | 否   | `720p`                                  | `480p`、`720p`、`720p-sr`、`720p-esr`、`1080p`、`1080p-sr`、`1080p-esr`、`1080p-esr & 60fps`、`1440p-sr`、`1440p-esr`、`4k-esr`、`4k` |
| `ratio`             | `aspect_ratio`（隐藏）                | 否   | `adaptive`                              | 沿用起始图宽高比                                                                                                                      |
| `output_format`     | `video_format`                        | 否   | `mp4`                                   | `mp4` 或 `mov`。MOV 使用 YUV 4:4:4                                                                                                    |
| `generate_audio`    | `generate_audio`                      | 否   | `true`                                  | 生成同步音频                                                                                                                          |
| `watermark`         | `add_watermark`                       | 否   | `false`                                 | 添加水印                                                                                                                              |
| `return_last_frame` | `include_last_frame`                  | 否   | `false`                                 | 另存尾帧图片                                                                                                                          |
| `draft`             | `draft`                               | 否   | `false`                                 | 开启时生成 480p 预览并返回草稿 ID                                                                                                     |

图片接受公开 URL、Base64（原始或 Data URI）和 `asset://<ASSET_ID>`。同时支持直接上传 JPEG、PNG、WebP、BMP、TIFF、GIF。单张图片边长 300 至 6,000 像素，宽高比 0.4 至 2.5，最多 30 MB。超过 ComfyShop 文本输入容量的 Base64 素材可直接上传。

`720p-sr` / `720p-esr` 基于原生 480p。`1080p-sr` / `1080p-esr` / `1080p-esr & 60fps` 基于原生 720p。`1440p-sr` / `1440p-esr` / `4k-esr` 基于原生 1080p，`4k-esr` 将短边增强至 2160 像素。不同原生与增强档位可有不同价格。

开启 `draft` 后，Atlas 以 480p 生成预览并按 480p 计费，覆盖请求分辨率。结果包含草稿 ID，七天内可用该 ID 生成 1080p 或 4K 正式版。[草稿转正式版](https://www.atlascloud.ai/models/bytedance/seedance-2.5/draft-complete)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedance-2.5-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedance-2.5-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedance-2.5-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-2.5-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedance-2.5/image-to-video#usage-examples)

```json
{
  "model": "bytedance/seedance-2.5/image-to-video",
  "prompt": "The scene comes alive with gentle motion and cinematic lighting",
  "image": "https://example.com/first-frame.png",
  "last_image": "https://example.com/last-frame.png",
  "duration": 5,
  "resolution": "720p",
  "ratio": "adaptive",
  "output_format": "mp4",
  "generate_audio": true,
  "watermark": false,
  "return_last_frame": false,
  "draft": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `data.outputs` 中的视频和可选尾帧。开启 `draft` 时另存仅含草稿 ID 的 TXT，可将其中的 ID 填入草稿转正式版工作流。若完成响应省略 `data.draft_id`，使用草稿的预测 ID。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首尾帧、提示词、时长和分辨率。高级参数为外部帧来源、同步音频、水印、尾帧、视频容器和草稿模式。画面比例固定为自适应。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
