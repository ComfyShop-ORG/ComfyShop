# OmniHuman 1.5 音频驱动人像

用一张人像和一段音频生成口型同步的视频，视频长度跟随音频。 Atlas Cloud 模型 ID 为 `bytedance/avatar-omni-human-v1.5`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/avatar-omni-human-v1.5)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                 | 必填 | 默认值                             | 输入约定                                        |
| ------------------- | ------------------------------ | ---- | ---------------------------------- | ----------------------------------------------- |
| `model`             | `execution.config.model`       | 是   | `bytedance/avatar-omni-human-v1.5` | 工作机从执行配置读取                            |
| `image_url`         | `portrait` 或 `portrait_url`   | 是   | —                                  | 人像图片上传或公开 URL，两者选一                |
| `audio_url`         | `driving_audio` 或 `audio_url` | 是   | —                                  | WAV 或 MP3 上传或公开 URL，两者选一。最多 60 秒 |
| `prompt`            | `prompt`                       | 否   | —                                  | 可描述动作、场景或表情，最多 2,000 字符         |
| `output_resolution` | `output_resolution`            | 否   | `1080`                             | 整数 `720` 或 `1080`                            |
| `seed`              | `seed`                         | 否   | `-1`                               | 整数，`-1` 由模型随机选取                       |

官方端点 Schema 的分辨率默认值为 `1080`，工作流遵循该值。驱动音频建议 15 秒以内。上传素材由工作机转为 API 所需的 URL。[上传接口](https://www.atlascloud.ai/docs/upload-files)

[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-avatar-omni-human-v1.5.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-avatar-omni-human-v1.5.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-avatar-omni-human-v1.5.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/avatar-omni-human-v1.5/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/avatar-omni-human-v1.5#usage-examples)

```json
{
  "model": "bytedance/avatar-omni-human-v1.5",
  "image_url": "https://static.atlascloud.ai/template/omnihuman/test_image.png",
  "audio_url": "https://static.atlascloud.ai/template/omnihuman/test_audio.mp3",
  "output_resolution": 1080,
  "seed": -1
}
```

从响应取 `id`（也可位于 `data.id`），优先轮询本模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`。端点返回 404 或 405 时改用通用的 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机保存 `outputs` 数组中的视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为人像、驱动音频和分辨率。高级参数为提示词、随机种子和外部素材 URL。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
