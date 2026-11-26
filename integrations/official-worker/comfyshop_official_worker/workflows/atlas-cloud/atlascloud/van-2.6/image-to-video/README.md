# Atlas Cloud Van 2.6 图生视频

从一张起始图生成 1080p 视频，可编排单镜头或多镜头，并使用参考音频。 Atlas Cloud 模型 ID 为 `atlascloud/van-2.6/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/van-2.6/image-to-video)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                        | 必填     | 默认值                              | 输入约定                                        |
| ------------------------- | ------------------------------------- | -------- | ----------------------------------- | ----------------------------------------------- |
| `model`                   | `execution.config.model`              | 是       | `atlascloud/van-2.6/image-to-video` | 工作机从执行配置读取                            |
| `image`                   | `first_frame` 或 `first_frame_source` | 是       | 无                                  | 上传起始图或填写可公开访问的图片 URL            |
| `prompt`                  | `prompt`                              | 是       | 无                                  | 描述主体动作、场景变化和镜头                    |
| `negative_prompt`         | `negative_prompt`                     | 否       | 无                                  | 描述希望避开的元素，留空时省略                  |
| `audio`                   | `soundtrack` 或 `soundtrack_source`   | 否       | 无                                  | 上传参考音频，或填写可公开访问的音频 URL        |
| `resolution`              | `resolution`                          | 是       | `1080p`                             | 固定为 `1080p`                                  |
| `duration`                | `duration`                            | 否       | 5                                   | `5`、`10` 或 `15` 秒                            |
| `enable_prompt_expansion` | `enable_prompt_expansion`             | 条件必填 | `true`                              | 启用提示词优化，`shot_type=multi` 时须为 `true` |
| `shot_type`               | `shot_type`                           | 否       | `multi`                             | `multi` 多镜头或 `single` 单镜头                |
| `generate_audio`          | `generate_audio`                      | 否       | `true`                              | 控制自动添加音频                                |
| `seed`                    | `seed`                                | 否       | -1                                  | 整数，-1 使用随机种子                           |

当前官方端点与 Schema 将分辨率限定为 `1080p`，时长枚举包含 15 秒。模型介绍还列出 720p 和 10 秒内的用法。工作机按模型页的示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-van-2.6-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-van-2.6-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-van-2.6-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/van-2.6-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/van-2.6/image-to-video#usage-examples)

```json
{
  "model": "atlascloud/van-2.6/image-to-video",
  "image": "https://example.com/harbor.png",
  "prompt": "镜头沿海面平稳向前移动，薄雾从画面右侧散开。",
  "resolution": "1080p",
  "duration": 10,
  "shot_type": "single",
  "enable_prompt_expansion": false,
  "generate_audio": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、提示词、时长和镜头模式位于默认区。图片来源、负面提示词、参考音频、提示词扩写、自动音频和种子位于高级区。工作机提交隐藏的固定分辨率。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
