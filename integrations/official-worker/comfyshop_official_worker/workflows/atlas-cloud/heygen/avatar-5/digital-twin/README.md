# HeyGen Avatar V 数字人视频

选择预设数字人，用脚本或音频生成对口型的演示视频。 Atlas Cloud 模型 ID 为 `heygen/avatar-5/digital-twin`。[官方模型 API](https://www.atlascloud.ai/models/heygen/avatar-5/digital-twin)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                      | 必填           | 默认值                         | 输入约定                                                            |
| ------------------- | ----------------------------------- | -------------- | ------------------------------ | ------------------------------------------------------------------- |
| `model`             | `execution.config.model`            | 是             | `heygen/avatar-5/digital-twin` | 工作机从执行配置读取                                                |
| `avatar`            | `avatar`                            | 否             | `Abigail Sofa Front`           | 497 个角色预设                                                      |
| `prompt`            | `prompt`                            | 与音频至少一项 | —                              | 要朗读的文字                                                        |
| `voice`             | `voice`                             | 否             | `Warm Pro Narrator`            | 102 个朗读音色。提供音频时由音频驱动                                |
| `audio`             | `voice_audio` 或 `audio_source`     | 与脚本至少一项 | —                              | 上传音频，或填写公开 URL、Base64 数据 URI 或原始 Base64             |
| `fit`               | `fit`                               | 否             | `cover`                        | `cover` 铺满，`contain` 完整显示                                    |
| `remove_background` | `remove_background`                 | 否             | `false`                        | 移除背景需要选用支持抠像的角色                                      |
| `background_color`  | `background_color`                  | 否             | —                              | 十六进制颜色，如 `#FFFFFF`                                          |
| `background_image`  | `background` 或 `background_source` | 否             | —                              | 上传图片，或填写公开 URL、Base64 数据 URI 或原始 Base64。优先于颜色 |
| `output_format`     | `output_format`                     | 否             | `mp4`                          | `mp4` 或透明 `webm`                                                 |
| `resolution`        | `resolution`                        | 否             | `720p`                         | `720p`、`1080p` 或 `4k`                                             |
| `aspect_ratio`      | `aspect_ratio`                      | 否             | `16:9`                         | `16:9`、`9:16`、`4:5`、`5:4`、`1:1`、`auto`                         |

角色与音色沿用 Atlas 的预设名称，发送原始枚举值。音频与脚本同时提供时 Atlas 使用音频，视频长度跟随实际朗读或音频时长。选择 WebM 时，工作机省略背景颜色和背景图片，Atlas 输出透明视频。原始渲染为 1080p，4K 选项导出放大后的版本。[官方模型说明](https://www.atlascloud.ai/models/heygen-avatar-v-digital-twin)

[官方 Schema](https://static.atlascloud.ai/model/schema/heygen-avatar-5-digital-twin.json) · [官方示例数据](https://static.atlascloud.ai/model/example/heygen-avatar-5-digital-twin.json)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/heygen/avatar-5/digital-twin#usage-examples)

```json
{
  "model": "heygen/avatar-5/digital-twin",
  "avatar": "Abigail Sofa Front",
  "prompt": "欢迎参加今天的产品演示。",
  "voice": "Warm Pro Narrator",
  "fit": "cover",
  "remove_background": false,
  "output_format": "mp4",
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括数字人、朗读脚本、音色、驱动音频、分辨率和宽高比。高级参数包括画面适配、背景、容器和外部素材地址。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
