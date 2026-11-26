# 可灵 4.0 自定义音色

从一段单人语音或已有可灵视频创建音色。工作流保存试听音频、可复制的音色 ID 和原始音色信息。Atlas Cloud 模型 ID 为 `kwaivgi/kling-v4.0/custom-voice`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段           | 必填   | 默认值                            | 输入约定                                                                                                    |
| ------------ | ------------------------ | ------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `model`      | `execution.config.model` | 是     | `kwaivgi/kling-v4.0/custom-voice` | 工作机从执行配置读取                                                                                        |
| `voice_name` | `voice_name`             | 是     | `My Voice`                        | 新音色名称，1 至 20 字符                                                                                    |
| `audio`      | `audio`                  | 二选一 | 无                                | 上传 5 至 30 秒的单人清晰语音。支持 MP3、WAV、MP4、MOV，文件不超过 50 MB。工作机上传到 Atlas 后发送素材 URL |
| `video_id`   | `video_id`               | 二选一 | 无                                | 使用带声音的可灵 V2.6、数字人或口型同步接口生成的已有视频 ID                                                |

只填写一种来源。工作机用平台识别到的时长校验新上传的样本。视频需要包含要使用的语音。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v4.0-custom-voice.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v4.0-custom-voice.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v4.0-custom-voice.md)

## API 调用

将以下示例发送到 `POST https://api.atlascloud.ai/api/v1/model/generateAudio`，使用 `Authorization: Bearer <API_KEY>`。示例地址替换为语音样本的可访问 URL。

```json
{
  "model": "kwaivgi/kling-v4.0/custom-voice",
  "voice_name": "纪录片旁白",
  "audio": "https://example.com/speech-sample.wav"
}
```

用预测编号轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。完成时读取试听音频 `outputs` 及音色详情 `voice_result`。工作机把 `voice_result.voice_id` 保存为文本，同时保存完整的 JSON。音色 ID 是 18 位数字组成的字符串。传给可灵 4.0 参考生视频或视频编辑接口的 `voice_ids` 时，保持字符串类型。试听地址也可由 `voice_result.trial_url` 提供。[官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

音色名称与上传语音位于默认区，已有视频 ID 位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
