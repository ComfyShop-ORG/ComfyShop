# LTX 2.3 Quality 文生视频

根据提示词生成视频，可指定帧数、画面尺寸并生成配套音频。 Atlas Cloud 模型 ID 为 `ltx-2.3-quality/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/ltx-2.3-quality/text-to-video)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段           | 必填 | 默认值                          | 输入约定                                                                                  |
| ---------------- | ------------------------ | ---- | ------------------------------- | ----------------------------------------------------------------------------------------- |
| `model`          | `execution.config.model` | 是   | `ltx-2.3-quality/text-to-video` | 工作机从执行配置读取                                                                      |
| `prompt`         | `prompt`                 | 是   | —                               | 非空文字，1 至 2,000 字符                                                                 |
| `num_frames`     | `num_frames`             | 否   | `121`                           | 整数 25–257，满足 `(num_frames - 1) % 8 == 0`                                             |
| `resolution`     | `resolution`             | 否   | `landscape_16_9`                | `square_hd`、`square`、`portrait_3_4`、`portrait_9_16`、`landscape_4_3`、`landscape_16_9` |
| `generate_audio` | `generate_audio`         | 否   | `false`                         | 生成同步音频                                                                              |
| `seed`           | `seed`                   | 否   | 由 Atlas 选取                   | 非负整数，留空时省略参数                                                                  |

121 帧按模型说明的 24 fps 约为 5 秒。画面尺寸值采用 Atlas 公开端点的枚举。调用方法采用官方模型页和端点文档中的 `generateVideo`。

[官方 Schema](https://static.atlascloud.ai/model/schema/ltx-2.3-quality-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/ltx-2.3-quality-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/ltx-2.3-quality-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/ltx-2.3-quality/text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/ltx-2.3-quality/text-to-video#usage-examples)

```json
{
  "model": "ltx-2.3-quality/text-to-video",
  "prompt": "海浪轻轻拍打岸边，镜头沿沙滩平稳推进。",
  "num_frames": 121,
  "resolution": "portrait_3_4",
  "generate_audio": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、帧数和画面尺寸。高级参数为同步音频和随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
