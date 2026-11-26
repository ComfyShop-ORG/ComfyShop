# 可灵 O3 专业版参考生视频

以图片、视频、主体和音色为参考生成原生 1080p 视频。可选择自动分镜或编排自定义分镜。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-video-o3-pro/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/reference-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                                      | 必填     | 默认值                                          | 输入约定                                                                                                                                          |
| -------------- | --------------------------------------------------- | -------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`        | `execution.config.model`                            | 是       | `kwaivgi/kling-video-o3-pro/reference-to-video` | 工作机从执行配置读取                                                                                                                              |
| `prompt`       | `prompt`                                            | 条件必填 | 省略                                            | 最多 2,500 字符。在单镜头和自动分镜模式下必填                                                                                                     |
| `video`        | `reference_video` 或 `video_source`                 | 否       | 省略                                            | 一条可公开访问或上传的 MP4 或 MOV，3 至 15.5 秒、24 至 60 帧每秒、最多 200 MB。每边 700 至 4,553 像素，总面积最多 8,294,400 像素，宽高比 0.4 至 2 |
| `images`       | `reference_1` 至 `reference_7`、`reference_sources` | 否       | 省略                                            | JPEG 或 PNG，最多 50 MB，每边至少 300 像素，宽高比 1:2.5 至 2.5:1。与图片主体合计最多 7 张，混合视频时最多 4 张                                   |
| `multi_shot`   | `multi_shot`                                        | 否       | `false`                                         | 开启后支持自动分镜。无参考视频时可提供自定义分镜                                                                                                  |
| `multi_prompt` | `multi_prompt`                                      | 否       | 省略                                            | 1 至 6 项分镜。每项提示词最多 512 字符，时长至少 1 秒且合计等于总时长。工作机按数组生成 `index`，以字符串提交每项 `duration`                      |
| `elements`     | `elements`                                          | 否       | 省略                                            | 最多 6 个主体，详见素材组合规则                                                                                                                   |
| `voice_ids`    | `voice_ids`                                         | 否       | 省略                                            | 最多 3 个已有或预设音色 ID，每行一个                                                                                                              |
| `aspect_ratio` | `aspect_ratio`                                      | 否       | `16:9`                                          | `16:9`、`9:16` 或 `1:1`                                                                                                                           |
| `duration`     | `duration`                                          | 否       | 5                                               | 3 至 15 秒，整数枚举                                                                                                                              |
| `sound`        | `sound`                                             | 否       | `false`                                         | 仅无参考视频时可生成同期声                                                                                                                        |

原生输出 1080p。工作机按目录 ID 与官方样例提交 `kwaivgi/kling-video-o3-pro/reference-to-video`，静态 Schema 的默认模型标识带有 `-test` 后缀。静态样例还带有 `keep_original_sound`，当前接口用 `sound` 控制同期声。工作机按模型页示例轮询 `prediction/{id}`。[可灵自定义音色](https://www.atlascloud.ai/models/kwaivgi/kling-v4.0/custom-voice) · [官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-video-o3-pro-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-video-o3-pro-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-video-o3-pro-reference-to-video.md)

## 素材组合

- 未提供参考视频时，可提交最多 3 个视频主体。参考图和图片主体合计最多 7 项，使用视频主体时合计最多 4 项。
- 提供参考视频时，可使用参考图和图片主体共最多 4 项，或仅使用一个视频主体。工作机省略 `sound`，并在多镜头模式下只接受自动分镜。
- 已有主体可通过 `element_id` 引用。新建图片主体需填写 `element_name`、`reference_type=image_refer`、`frontal_image` 和 1 至 3 个 `refer_images`。视频主体需填写 `element_name`、`reference_type=video_refer` 和 1 个 `refer_videos`。新建主体支持选填 `element_description`。
- 参考图先按上传槽顺序提交，再提交填写的 URL，编号跳过空槽。用 `<<<image_1>>>`、`<<<video_1>>>`、`<<<element_1>>>`、`<<<voice_1>>>` 等在提示词中引用。工作机按已知类型校验素材数，已有主体仅按 ID 引用时由 Atlas 确认类型。工作机校验可用的素材宽高和时长，帧率由 Atlas 校验。

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-video-o3-pro-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/reference-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-video-o3-pro/reference-to-video",
  "images": ["https://example.com/bicycle.jpg"],
  "prompt": "让 <<<image_1>>> 中的自行车出现在细雨后的街角，镜头平稳拉远。",
  "aspect_ratio": "16:9",
  "duration": 5,
  "multi_shot": false,
  "sound": false
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、参考视频、第一张参考图、画面比例、时长和多镜头位于默认区。更多素材、分镜、主体、音色及同期声位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
