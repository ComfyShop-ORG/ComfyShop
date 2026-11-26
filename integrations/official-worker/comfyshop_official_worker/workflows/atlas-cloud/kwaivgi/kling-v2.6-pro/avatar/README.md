# 可灵 2.6 专业版数字人

用人物图和语音生成口型同步视频，成品时长由语音决定。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v2.6-pro/avatar`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v2.6-pro/avatar)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段                  | 必填 | 默认值                          | 输入约定                                   |
| ---------- | ------------------------------- | ---- | ------------------------------- | ------------------------------------------ |
| `model`    | `execution.config.model`        | 是   | `kwaivgi/kling-v2.6-pro/avatar` | 工作机从执行配置读取                       |
| `image`    | `portrait` 或 `portrait_source` | 是   | 无                              | 上传清晰的人物图或填写公开图片 URL         |
| `audio`    | `voice` 或 `voice_source`       | 是   | 无                              | 上传驱动语音或填写公开音频 URL             |
| `prompt`   | `prompt`                        | 否   | 省略                            | 可描述人物表情、风格与镜头氛围，空值时省略 |

Atlas 根据音频时长生成口型同步视频。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v2.6-pro-avatar.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v2.6-pro-avatar.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v2.6-pro-avatar.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v2.6-pro-avatar/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v2.6-pro/avatar#usage-examples)

```json
{
  "model": "kwaivgi/kling-v2.6-pro/avatar",
  "image": "https://example.com/portrait.png",
  "audio": "https://example.com/speech.mp3",
  "prompt": "人物面向镜头自然讲解，轻微点头。"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

人物图、驱动语音和表演提示词位于默认区。素材 URL 位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
