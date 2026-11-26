# MiniMax H3 Fast 文生视频

根据提示词生成 5 至 15 秒的 480P 视频。Atlas Cloud 模型 ID 为 `minimax/h3-fast/text-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-fast/text-to-video)

## 官方参数

| Atlas 参数         | ComfyShop 字段           | 必填 | 默认值                          | 输入约定                                    |
| ------------------ | ------------------------ | ---- | ------------------------------- | ------------------------------------------- |
| `model`            | `execution.config.model` | 是   | `minimax/h3-fast/text-to-video` | 工作机从执行配置读取                        |
| `prompt`           | `prompt`                 | 是   | 由用户填写                      | 描述主体、场景与镜头运动                    |
| `duration`         | `duration_seconds`       | 是   | `8`                             | 5 至 15 秒的整数                            |
| `resolution`       | `resolution`             | 是   | `480P`                          | 唯一枚举为 `480P`                           |
| `ratio`            | `aspect_ratio`           | 否   | `1:1`                           | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |
| `prompt_expansion` | `expand_prompt`          | 否   | `false`                         | 是否在生成前扩写提示词                      |

参数来自 Atlas Cloud 请求定义。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-fast-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-fast-text-to-video.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/h3-fast/text-to-video",
  "prompt": "镜头掠过海边的长廊，落日照亮远处的帆船。",
  "duration": 8,
  "resolution": "480P",
  "ratio": "1:1",
  "prompt_expansion": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 获取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-fast/text-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、时长和画面比例在默认区，扩写开关在高级区，固定分辨率在隐藏区。维护账号可通过「编辑参数」调整布局、说明与默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
