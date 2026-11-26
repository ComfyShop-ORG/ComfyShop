# Atlas Cloud Van 2.5 文生视频

用文字生成 5 或 10 秒的视频，支持横屏、竖屏和参考音频。 Atlas Cloud 模型 ID 为 `atlascloud/van-2.5/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/van-2.5/text-to-video)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                      | 必填 | 默认值                             | 输入约定                                         |
| ------------------------- | ----------------------------------- | ---- | ---------------------------------- | ------------------------------------------------ |
| `model`                   | `execution.config.model`            | 是   | `atlascloud/van-2.5/text-to-video` | 工作机从执行配置读取                             |
| `prompt`                  | `prompt`                            | 是   | 无                                 | 描述主体动作、场景变化和镜头                     |
| `negative_prompt`         | `negative_prompt`                   | 否   | 无                                 | 描述希望避开的元素，留空时省略                   |
| `audio`                   | `soundtrack` 或 `soundtrack_source` | 否   | 无                                 | 上传参考音频，或填写可公开访问的音频 URL         |
| `size`                    | `size`                              | 是   | `1280*720`                         | `1280*720`、`720*1280`、`1920*1080`、`1080*1920` |
| `duration`                | `duration`                          | 否   | 5                                  | `5` 或 `10` 秒                                   |
| `enable_prompt_expansion` | `enable_prompt_expansion`           | 否   | `false`                            | 开启提示词优化和扩写                             |
| `seed`                    | `seed`                              | 否   | -1                                 | 整数，-1 使用随机种子                            |

尺寸以当前端点列出的四种像素预设为准。工作机按模型页的示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-van-2.5-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-van-2.5-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-van-2.5-text-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/van-2.5-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/van-2.5/text-to-video#usage-examples)

```json
{
  "model": "atlascloud/van-2.5/text-to-video",
  "prompt": "午后的光线照在蓝色玻璃杯上，镜头缓慢绕杯移动。",
  "size": "1280*720",
  "duration": 5,
  "enable_prompt_expansion": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、尺寸和时长位于默认区。负面提示词、参考音频、提示词扩写和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
