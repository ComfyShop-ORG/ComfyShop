# MiniMax H3 Max Turbo 文生视频

根据提示词生成 5 至 15 秒的视频，可设置 480P 或 768P 分辨率和画面比例。Atlas Cloud 模型 ID 为 `minimax/h3-max-turbo/text-to-video`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-max-turbo/text-to-video)

## 官方参数

| Atlas 参数   | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                    |
| ------------ | ------------------------ | ---- | ------------------------------------ | ------------------------------------------- |
| `model`      | `execution.config.model` | 是   | `minimax/h3-max-turbo/text-to-video` | 工作机从执行配置读取                        |
| `prompt`     | `prompt`                 | 是   | 由用户填写                           | 描述主体、场景和镜头运动                    |
| `duration`   | `duration_seconds`       | 是   | `8`                                  | 5 至 15 秒，按整数枚举提交                  |
| `resolution` | `resolution`             | 是   | `768P`                               | `480P`、`768P`                              |
| `ratio`      | `aspect_ratio`           | 否   | `1:1`                                | `21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16` |

枚举和默认值以 Atlas Cloud 请求 Schema 为准。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-max-turbo-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-max-turbo-text-to-video.json)

## API 调用

将 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`，使用 `Authorization: Bearer <API_KEY>`。示例使用 480P 和竖屏比例。

```json
{
  "model": "minimax/h3-max-turbo/text-to-video",
  "prompt": "镜头从雨后的窗边向外推进，远处的有轨电车驶过街角。",
  "duration": 8,
  "resolution": "480P",
  "ratio": "9:16"
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，在 `data.outputs` 获取视频地址。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-max-turbo/text-to-video#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/en/predictions)

## ComfyShop 同步

字段标签与提示随展示语言切换。所有字段均列入默认参数，维护账号可通过「编辑参数」调整布局与默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
