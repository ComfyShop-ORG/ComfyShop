# Wan 2.5 Fast 图生视频

用起始图和提示词生成视频，可选择分辨率和参考音频。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.5/image-to-video-fast`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.5/image-to-video-fast)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                        | 必填 | 默认值                                | 输入约定                                                                                                      |
| ------------------------- | ------------------------------------- | ---- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`              | 是   | `alibaba/wan-2.5/image-to-video-fast` | 工作机从执行配置读取                                                                                          |
| `image`                   | `first_frame` 或 `first_frame_source` | 是   | 无                                    | 上传或使用公开 URL、Base64 数据网址。JPEG、无透明通道的 PNG、BMP 或 WebP，宽高各 240 至 8000 像素，最多 20 MB |
| `prompt`                  | `prompt`                              | 是   | 无                                    | 最多 1,500 字符                                                                                               |
| `negative_prompt`         | `negative_prompt`                     | 否   | 无                                    | 最多 500 字符，留空时省略                                                                                     |
| `audio`                   | `soundtrack` 或 `soundtrack_source`   | 否   | 无                                    | WAV 或 MP3，3 至 30 秒且最多 15 MB。上传或填写公开 URL                                                        |
| `resolution`              | `resolution`                          | 是   | `720p`                                | `720p` 或 `1080p`                                                                                             |
| `duration`                | `duration`                            | 否   | 5                                     | `5` 或 `10` 秒                                                                                                |
| `enable_prompt_expansion` | `enable_prompt_expansion`             | 否   | false                                 | 启用提示词优化                                                                                                |
| `seed`                    | `seed`                                | 否   | -1                                    | 整数，范围 -1 至 2147483647。-1 使用随机种子                                                                  |

工作机按模型页调用示例轮询 `prediction/{id}`。静态 Schema 的旧路径为 `result/{id}`。素材和提示词限制参照厂商的 Wan 2.5 Fast 约定。[阿里云图生视频参数](https://www.alibabacloud.com/help/en/model-studio/legacy-image-to-video-api-reference/) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.5-image-to-video-fast.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.5-image-to-video-fast.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.5-image-to-video-fast.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.5-image-to-video-fast/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.5/image-to-video-fast#usage-examples)

```json
{
  "model": "alibaba/wan-2.5/image-to-video-fast",
  "image": "https://example.com/glass.webp",
  "prompt": "让画面中的玻璃杯落入浅水，镜头保持在水面附近，慢动作拍摄溅起的水滴。",
  "audio": "https://example.com/splash.wav",
  "resolution": "720p",
  "duration": 5,
  "enable_prompt_expansion": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、分辨率、时长位于默认区。素材来源、负面提示词、参考音频、扩写与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
