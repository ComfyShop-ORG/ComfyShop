# 可灵 3.0 4K 文生视频

用文字生成原生 4K 视频，可选择画面比例和单镜头或多镜头。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v3.0-4k/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-4k/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填     | 默认值                                | 输入约定                                                                                  |
| -------------- | ------------------------ | -------- | ------------------------------------- | ----------------------------------------------------------------------------------------- |
| `model`        | `execution.config.model` | 是       | `kwaivgi/kling-v3.0-4k/text-to-video` | 工作机从执行配置读取                                                                      |
| `prompt`       | `prompt`                 | 条件必填 | 省略                                  | 最多 2,500 字符。在单镜头和自动分镜模式下必填                                             |
| `aspect_ratio` | `aspect_ratio`           | 否       | `16:9`                                | `16:9`、`9:16` 或 `1:1`                                                                   |
| `duration`     | `duration`               | 否       | 5                                     | 3 至 15 秒，整数枚举                                                                      |
| `multi_shot`   | `multi_shot`             | 否       | `false`                               | 开启后支持自动或自定义分镜                                                                |
| `multi_prompt` | `multi_prompt`           | 否       | 省略                                  | 仅多镜头时提交。以 1 至 6 项的 JSON 数组编辑，每项填写 `prompt`、`duration`，可选 `index` |
| `sound`        | `sound`                  | 否       | `true`                                | 生成同步声音                                                                              |

原生输出固定为 4K。静态示例另有 `cfg_scale`，请求参数以上表为准。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v3.0-4k-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v3.0-4k-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v3.0-4k-text-to-video.md)

## 分镜参数

- `multi_prompt` 按数组顺序提交。每个镜头的 `prompt` 最多 512 字符，`duration` 以至少 1 秒的整数提交，各段之和须等于视频总时长。开启多镜头并提供分镜时，分镜优先于顶层提示词。开启多镜头且省略分镜时，Atlas 按提示词自动分镜。

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v3.0-4k-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-4k/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v3.0-4k/text-to-video",
  "aspect_ratio": "16:9",
  "duration": 5,
  "multi_shot": true,
  "multi_prompt": [
    {
      "prompt": "远景展示天色渐亮时海边的白色灯塔。",
      "duration": 2
    },
    {
      "prompt": "切近灯塔窗口，镜头在玻璃上的水珠间缓慢移动。",
      "duration": 3
    }
  ],
  "sound": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例、时长和多镜头位于默认区。分镜方案及声音位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
