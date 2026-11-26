# Atlas Cloud InfiniteTalk 语音驱动视频

用一张人物图片和一段语音生成口型同步视频，可描述表情与姿势。 Atlas Cloud 模型 ID 为 `atlascloud/infinitetalk`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/infinitetalk)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                  | 必填 | 默认值                    | 输入约定                                                  |
| ------------ | ------------------------------- | ---- | ------------------------- | --------------------------------------------------------- |
| `model`      | `execution.config.model`        | 是   | `atlascloud/infinitetalk` | 工作机从执行配置读取                                      |
| `image`      | `portrait` 或 `portrait_source` | 是   | 无                        | 上传人物图片或填写公开图片 URL                            |
| `audio`      | `voice` 或 `voice_source`       | 是   | 无                        | 上传 WAV 或 MP3，或填写公开语音 URL。上传音频最长 10 分钟 |
| `prompt`     | `prompt`                        | 否   | 省略                      | 描述表情、姿势或动作，空值时省略                          |
| `resolution` | `resolution`                    | 否   | `480p`                    | `480p` 或 `720p`                                          |
| `seed`       | `seed`                          | 否   | -1                        | 整数，-1 使用随机种子                                     |

公开 API 接收一张人物图片和一段语音。模型介绍还列有双人和视频参考能力，公开请求定义仅提供上表中的素材字段。模型介绍给出的成片上限为 10 分钟。工作机通过该工作流的 `prediction_timeout_seconds` 最多等待 6 小时，以覆盖长音频处理。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-infinitetalk.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-infinitetalk.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-infinitetalk.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/atlascloud/infinitetalk#usage-examples)

```json
{
  "model": "atlascloud/infinitetalk",
  "image": "https://example.com/portrait.png",
  "audio": "https://example.com/speech.wav",
  "prompt": "人物面向镜头自然讲话，微微点头。",
  "resolution": "480p",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

人物图片、驱动语音、表演提示词和分辨率位于默认区。素材 URL 和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
