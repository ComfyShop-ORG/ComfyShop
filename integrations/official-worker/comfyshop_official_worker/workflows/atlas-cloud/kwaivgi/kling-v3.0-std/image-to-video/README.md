# 可灵 3.0 标准版图生视频

用起始图生成原生 720p 视频，可指定结束帧、分镜和主体引用。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-v3.0-std/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-std/image-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段                        | 必填     | 默认值                                  | 输入约定                                                                                                   |
| -------------- | ------------------------------------- | -------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `model`        | `execution.config.model`              | 是       | `kwaivgi/kling-v3.0-std/image-to-video` | 工作机从执行配置读取                                                                                       |
| `image`        | `first_frame` 或 `first_frame_source` | 是       | 无                                      | JPEG 或 PNG，每边至少 300 像素，宽高比 1:2.5 至 2.5:1，上传最多 50 MB。也可提供公开 URL                    |
| `end_image`    | `last_frame` 或 `last_frame_source`   | 否       | 省略                                    | 结束图，JPEG 或 PNG，每边至少 300 像素，上传最多 50 MB                                                     |
| `prompt`       | `prompt`                              | 条件必填 | 省略                                    | 最多 2,500 字符。在单镜头和自动分镜模式下必填                                                              |
| `duration`     | `duration`                            | 否       | 5                                       | 3 至 15 秒，整数枚举                                                                                       |
| `multi_shot`   | `multi_shot`                          | 否       | `false`                                 | 开启后支持自动或自定义分镜                                                                                 |
| `multi_prompt` | `multi_prompt`                        | 否       | 省略                                    | 仅多镜头时提交。以 1 至 6 项的 JSON 数组编辑，每项填写 `prompt`、`duration`，工作机补齐从 1 开始的 `index` |
| `elements`     | `elements`                            | 否       | 省略                                    | 至多 3 项，按数组顺序引用主体                                                                              |
| `sound`        | `sound`                               | 否       | `true`                                  | 生成同步声音                                                                                               |

原生输出固定为 720p。静态示例另有 `cfg_scale`，请求参数以上表为准。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-v3.0-std-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-v3.0-std-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-v3.0-std-image-to-video.md)

## 分镜与主体参数

- `multi_prompt` 按数组顺序提交。每个镜头的 `prompt` 最多 512 字符，输入时长为 1 至 15 秒，工作机按顺序补齐 `index` 并以字符串提交各段 `duration`，各段之和须等于视频总时长。开启多镜头并提供分镜时，分镜优先于顶层提示词。开启多镜头且省略分镜时，Atlas 按提示词自动分镜。
- 使用已有主体时填写 `element_id`，为正的 64 位整数。新建主体填写 `element_name` 和 `reference_type`，可附加 `element_description`。两种标识互斥。
- 新建图片主体使用 `reference_type=image_refer`，填写 `frontal_image` 和 1 至 4 个 `refer_images` URL。新建视频主体使用 `reference_type=video_refer`，填写 1 至 4 个 `refer_videos` URL。当前模型 API 页和 Schema 给出每组最多 4 项，静态模型介绍分别写为 3 张参考图和 1 条参考视频。
- 按主体在数组里的位置使用 `<<<element_1>>>`、`<<<element_2>>>` 等引用，可填写在顶层或分镜提示词中。

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-v3.0-std-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-v3.0-std/image-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-v3.0-std/image-to-video",
  "image": "https://example.com/start.jpg",
  "end_image": "https://example.com/end.png",
  "duration": 5,
  "multi_shot": true,
  "multi_prompt": [
    {
      "index": 1,
      "prompt": "镜头在石阶前缓慢推进，主体为 <<<element_1>>>。",
      "duration": "2"
    },
    {
      "index": 2,
      "prompt": "镜头移到侧面，沿植被和石阶上移。",
      "duration": "3"
    }
  ],
  "elements": [
    {
      "element_name": "花园雕塑",
      "reference_type": "image_refer",
      "frontal_image": "https://example.com/sculpture-front.png",
      "refer_images": ["https://example.com/sculpture-side.png"],
      "element_description": "一尊深灰色的几何雕塑"
    }
  ],
  "sound": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、结束图、提示词、时长和多镜头位于默认区。素材 URL、分镜方案、主体引用及声音位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
