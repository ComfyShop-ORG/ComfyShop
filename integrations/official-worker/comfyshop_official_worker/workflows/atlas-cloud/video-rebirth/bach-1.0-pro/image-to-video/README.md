# Bach 1.0 Pro 图生视频

提供首帧、尾帧或两张图片，生成 5 至 16 秒的视频。 Atlas Cloud 模型 ID 为 `video-rebirth/bach-1.0-pro/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/image-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                      | 必填           | 默认值                                            | 输入约定                            |
| ---------------- | ----------------------------------- | -------------- | ------------------------------------------------- | ----------------------------------- |
| `model`          | `execution.config.model`            | 是             | `video-rebirth/bach-1.0-pro/image-to-video`       | 工作机从执行配置读取                |
| `image`          | `first_frame`、`first_frame_source` | 与尾帧至少一项 | —                                                 | 首帧，JPEG、PNG 或 WebP，最多 10 MB |
| `last_image`     | `last_frame`、`last_frame_source`   | 与首帧至少一项 | —                                                 | 尾帧，JPEG、PNG 或 WebP，最多 10 MB |
| `prompt`         | `prompt`                            | 是             | `Continue naturally between the endpoint frames.` | 最多 6,500 字符                     |
| `duration`       | `duration`                          | 否             | `5`                                               | 5 至 16 秒的整数                    |
| `resolution`     | `resolution`                        | 否             | `1080p`                                           | `1080p` 或 `4k`                     |
| `generate_audio` | `generate_audio`                    | 否             | `true`                                            | 关闭后输出静音视频                  |
| `seed`           | `seed`                              | 否             | 随机                                              | 1 至 100,000 的整数                 |

首帧与尾帧至少填写一项。工作机接受上传文件、公开图片 URL、Base64 数据 URI 或原始 Base64。两帧均填写时，输出在它们之间过渡。画面比例由输入素材确定。

[官方 Schema](https://static.atlascloud.ai/model/schema/video-rebirth-bach-1.0-pro-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/video-rebirth-bach-1.0-pro-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/video-rebirth-bach-1.0-pro-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/video-rebirth/bach-1.0-pro/image-to-video#usage-examples)

```json
{
  "model": "video-rebirth/bach-1.0-pro/image-to-video",
  "image": "https://static.atlascloud.ai/media/images/006f3c02da3faaa0e3875285b3aad5e4.jpg",
  "last_image": "https://static.atlascloud.ai/media/images/04ef2d6187a86dc5703d5cebdc6daa10.jpg",
  "prompt": "Continue naturally between the endpoint frames.",
  "duration": 5,
  "resolution": "1080p",
  "generate_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括两帧图片、提示词、时长和分辨率。高级参数包括音频、随机种子和图片来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
