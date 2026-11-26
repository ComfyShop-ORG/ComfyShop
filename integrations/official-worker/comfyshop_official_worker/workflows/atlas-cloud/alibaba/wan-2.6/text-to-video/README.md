# Wan 2.6 文生视频

根据提示词生成视频，可选择尺寸、时长、镜头模式和音频。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.6/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.6/text-to-video)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                      | 必填     | 默认值                          | 输入约定                                                                                                                   |
| ------------------------- | ----------------------------------- | -------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`            | 是       | `alibaba/wan-2.6/text-to-video` | 工作机从执行配置读取                                                                                                       |
| `prompt`                  | `prompt`                            | 是       | 无                              | 最多 1,500 字符                                                                                                            |
| `negative_prompt`         | `negative_prompt`                   | 否       | 无                              | 最多 500 字符，留空时省略                                                                                                  |
| `audio`                   | `soundtrack` 或 `soundtrack_source` | 否       | 无                              | WAV 或 MP3，3 至 30 秒且最多 15 MB。上传或填写公开 URL                                                                     |
| `size`                    | `size`                              | 是       | `1280*720`                      | `1280*720`、`720*1280`、`960*960`、`1088*832`、`832*1088`、`1920*1080`、`1080*1920`、`1440*1440`、`1632*1248`、`1248*1632` |
| `duration`                | `duration`                          | 否       | 5                               | `5`、`10` 或 `15` 秒                                                                                                       |
| `enable_prompt_expansion` | `enable_prompt_expansion`           | 条件必填 | true                            | 控制提示词优化，`shot_type=multi` 时须为 `true`                                                                            |
| `shot_type`               | `shot_type`                         | 否       | `multi`                         | `multi` 多镜头或 `single` 单镜头                                                                                           |
| `generate_audio`          | `generate_audio`                    | 否       | true                            | 控制成品是否带音频                                                                                                         |
| `seed`                    | `seed`                              | 否       | -1                              | 整数范围 -1 至 2147483647。-1 使用随机种子                                                                                 |

尺寸使用宽*高的预设值。音频和提示词限制参照厂商的文生视频约定。[阿里云文生视频参数](https://www.alibabacloud.com/help/en/model-studio/legacy-wan-text-to-video-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.6-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.6-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.6-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.6-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.6/text-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-2.6/text-to-video",
  "prompt": "先从高处俯拍安静的山村，再切到传统屋檐下，雨水从瓦片边缘滴落。",
  "size": "1920*1080",
  "duration": 10,
  "enable_prompt_expansion": true,
  "shot_type": "multi",
  "generate_audio": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、尺寸、时长和镜头模式位于默认区。负面提示词、参考音频、扩写、音频开关与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
