# Grok Imagine Video v1.5 参考生视频

用 1 至 7 张参考图和文字生成最长 15 秒的视频，可指定预设对话音色。 Atlas Cloud 模型 ID 为 `xai/grok-imagine-video-v1.5/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5/reference-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                                              | 必填 | 默认值                                           | 输入约定                                           |
| -------------- | ----------------------------------------------------------- | ---- | ------------------------------------------------ | -------------------------------------------------- |
| `model`        | `execution.config.model`                                    | 是   | `xai/grok-imagine-video-v1.5/reference-to-video` | 工作机从执行配置读取                               |
| `prompt`       | `prompt`                                                    | 是   | —                                                | 用 `<IMAGE_0>`、`<IMAGE_1>` 等按提交顺序引用参考图 |
| `image_urls`   | `reference_image_1` 至 `reference_image_7`，`image_sources` | 是   | —                                                | 1 至 7 张，接受公开 HTTPS URL 或 Base64 Data URI   |
| `duration`     | `duration_seconds`                                          | 否   | `8`                                              | 整数 1 至 15 秒                                    |
| `resolution`   | `resolution`                                                | 否   | `720p`                                           | `480p` 或 `720p`                                   |
| `aspect_ratio` | `aspect_ratio`                                              | 否   | `16:9`                                           | `1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`  |
| `voice_ids`    | `voice_1`、`voice_2`、`voice_3`                             | 否   | 省略                                             | 按槽位顺序传入 1 至 3 个多语言预设 xAI 音色 ID     |

上传图片或粘贴 Data URI 时支持 JPEG、PNG、WebP。外部来源每行填写一个，按上传槽位在前、外部来源在后的顺序提交。

预设音色有 `altair`、`ara`、`atlas`、`carina`、`castor`、`celeste`、`cosmo`、`eve`、`helios`、`helix`、`iris`、`kepler`、`leo`、`lumen`、`luna`、`lux`、`naksh`、`orion`、`perseus`、`rex`、`rigel`、`sal`、`sirius`、`ursa`、`zagan`、`zenith`。全部留空时省略 `voice_ids`。

[官方 Schema](https://static.atlascloud.ai/model/schema/xai-grok-imagine-video-v1.5-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/xai-grok-imagine-video-v1.5-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/xai-grok-imagine-video-v1.5-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/xai/grok-imagine-video-v1.5-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/xai/grok-imagine-video-v1.5/reference-to-video#usage-examples)

```json
{
  "model": "xai/grok-imagine-video-v1.5/reference-to-video",
  "prompt": "The speaker from <IMAGE_0> greets the audience and describes the harbor.",
  "image_urls": ["https://example.com/speaker.png"],
  "voice_ids": ["ara"],
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、第一张参考图、时长、分辨率和画面比例。高级参数为额外参考图、外部来源和对话音色。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
