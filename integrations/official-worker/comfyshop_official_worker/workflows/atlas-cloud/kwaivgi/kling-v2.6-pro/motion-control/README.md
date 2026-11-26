# 可灵 2.6 专业版动作控制

用人物参考图确定外观，用参考视频驱动动作。可选择朝向和是否保留参考视频声音。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v2.6-pro/motion-control`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v2.6-pro/motion-control)

## Atlas 接口参数

| Atlas 参数              | ComfyShop 字段                      | 必填 | 默认值                                  | 输入约定                                                                                        |
| ----------------------- | ----------------------------------- | ---- | --------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `model`                 | `execution.config.model`            | 是   | `kwaivgi/kling-v2.6-pro/motion-control` | 工作机从执行配置读取                                                                            |
| `image`                 | `appearance` 或 `appearance_source` | 是   | 无                                      | JPEG 或 PNG，每边至少 300 像素，宽高比 1:2.5 至 2.5:1，最多 50 MB。支持上传、公开 URL 和 Base64 |
| `video`                 | `motion` 或 `motion_source`         | 是   | 无                                      | MP4 或 MOV，每边 340 至 3,850 像素，最多 100 MB。至少 3 秒，最长时长随人物朝向改变              |
| `character_orientation` | `character_orientation`             | 是   | 表单预选 `image`                        | `image` 跟随参考图，视频最长 10 秒。`video` 跟随参考视频，最长 30 秒                            |
| `prompt`                | `prompt`                            | 否   | 省略                                    | 描述场景、元素、效果或希望避开的内容，最多 2,500 字符                                           |
| `keep_original_audio`   | `keep_original_audio`               | 否   | `true`                                  | 保留参考视频音轨，`false` 输出静音视频                                                          |

人物朝向在 Atlas API 中是必填项。填写 Base64 时，遵循 ComfyShop 单文本框的 4 MiB 上限。大图可直接上传或使用公开 URL。当前模型页和 Schema 定义音轨字段为 `keep_original_audio`，静态样例和较早的端点文档使用 `keep_original_sound`。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v2.6-pro-motion-control.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v2.6-pro-motion-control.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v2.6-pro-motion-control.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v2.6-pro-motion-control/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v2.6-pro/motion-control#usage-examples)

```json
{
  "model": "kwaivgi/kling-v2.6-pro/motion-control",
  "image": "https://example.com/character.png",
  "video": "https://example.com/motion.mp4",
  "character_orientation": "video",
  "prompt": "保留参考动作，在室内自然光下呈现。",
  "keep_original_audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

人物参考图、动作参考视频、人物朝向和提示词位于默认区。素材地址及声音选项位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
