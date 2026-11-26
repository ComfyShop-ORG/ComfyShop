# Wan 3.0 Prime 文生视频

用文字生成视频，可设置时长、比例、音频和最高 4K ESR。 Atlas Cloud 模型 ID 为 `alibaba/wan-3.0-prime/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/text-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段           | 必填 | 默认值                                | 输入约定                                                                         |
| ------------ | ------------------------ | ---- | ------------------------------------- | -------------------------------------------------------------------------------- |
| `model`      | `execution.config.model` | 是   | `alibaba/wan-3.0-prime/text-to-video` | 工作机从执行配置读取                                                             |
| `prompt`     | `prompt`                 | 是   | 无                                    | 描述主体、场景、动作和运镜，最多 20,000 字符                                     |
| `resolution` | `resolution`             | 否   | `1080p`                               | 原生 `480p`、`720p`、`1080p`。ESR `720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr` |
| `duration`   | `duration`               | 否   | 5                                     | 2 至 30 秒，`-1` 为自动时长                                                      |
| `ratio`      | `ratio`                  | 否   | `adaptive`                            | `adaptive`、`16:9`、`4:3`、`1:1`、`3:4` 或 `9:16`                                |
| `audio`      | `audio`                  | 否   | true                                  | 控制是否生成音轨                                                                 |
| `seed`       | `seed`                   | 否   | 由模型决定                            | 整数。`-1` 使用随机种子，留空时省略                                              |

分辨率按 Schema 提交小写值，示例数据中使用了大写 `720P`。ESR 选项由模型放大画面。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-3.0-prime-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-3.0-prime-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-3.0-prime-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-3.0-prime/text-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-3.0-prime/text-to-video",
  "prompt": "一只纸船沿雨后的小溪漂过，镜头贴近水面跟随，背景是细小的水流声。",
  "resolution": "1080p",
  "duration": 5,
  "ratio": "16:9",
  "audio": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、分辨率、时长和比例位于默认区。音频与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
