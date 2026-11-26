# OmniHuman 2.0 音频驱动人像

用一张图片和一段说话或唱歌音频生成视频，视频时长跟随音频。 Atlas Cloud 模型 ID 为 `bytedance/avatar-omni-human-v2.0`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/avatar-omni-human-v2.0)

## Atlas 接口参数

| Atlas 参数  | ComfyShop 字段                    | 必填 | 默认值                             | 输入约定                                                                       |
| ----------- | --------------------------------- | ---- | ---------------------------------- | ------------------------------------------------------------------------------ |
| `model`     | `execution.config.model`          | 是   | `bytedance/avatar-omni-human-v2.0` | 工作机从执行配置读取                                                           |
| `image`     | `portrait` 或 `portrait_source`   | 是   | —                                  | 上传、公开 HTTP(S) URL 或 Base64，任选一种                                     |
| `audio`     | `driving_audio` 或 `audio_source` | 是   | —                                  | 上传、公开 HTTP(S) URL 或 Base64，任选一种                                     |
| `prompt`    | `prompt`                          | 否   | —                                  | 描述场景、动作、手势或镜头。支持中文、英文、日文、韩文、墨西哥西班牙语和印尼语 |
| `watermark` | `add_watermark`                   | 否   | `false`                            | 添加水印                                                                       |

图片接受 JPEG、PNG、WebP、BMP、TIFF、GIF、HEIC 和 HEIF，单张小于 30 MB，宽高各 300–6,000 像素，宽高比 0.4–2.5。音频接受 WAV 或 MP3，长 4–300 秒，单段小于 15 MB。视频时长和 Atlas 计费以音频时长为准。超过 ComfyShop 文本输入容量的 Base64 素材可直接上传。[上传接口](https://www.atlascloud.ai/docs/upload-files)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-avatar-omni-human-v2.0.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-avatar-omni-human-v2.0.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-avatar-omni-human-v2.0.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/bytedance/avatar-omni-human-v2.0#usage-examples)

```json
{
  "model": "bytedance/avatar-omni-human-v2.0",
  "image": "https://example.com/portrait.png",
  "audio": "https://example.com/speech.wav",
  "watermark": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为人物图片和驱动音频。高级参数为提示词、外部素材来源和水印。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
