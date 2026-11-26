# 可灵 O3 专业版 文生视频

用文字生成 1080p 视频，可指定画面比例、分镜和主体引用。 Atlas Cloud 模型 ID 为 `kwaivgi/kling-video-o3-pro/text-to-video`。[官方模型 API](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/text-to-video)

## Atlas 接口参数

| Atlas 参数     | ComfyShop 字段           | 必填     | 默认值                                     | 输入约定                                                                                                     |
| -------------- | ------------------------ | -------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `model`        | `execution.config.model` | 是       | `kwaivgi/kling-video-o3-pro/text-to-video` | 工作机从执行配置读取                                                                                         |
| `prompt`       | `prompt`                 | 条件必填 | 省略                                       | 最多 2,500 字符。在单镜头和自动分镜模式下必填                                                                |
| `aspect_ratio` | `aspect_ratio`           | 否       | `16:9`                                     | `16:9`、`9:16` 或 `1:1`                                                                                      |
| `duration`     | `duration`               | 否       | 5                                          | 3 至 15 秒，整数枚举                                                                                         |
| `multi_shot`   | `multi_shot`             | 否       | `false`                                    | 开启后支持自动或自定义分镜                                                                                   |
| `multi_prompt` | `multi_prompt`           | 否       | 省略                                       | 仅多镜头时提交。以 1 至 6 项的 JSON 数组编辑，每项填写 `prompt` 和 `duration`。工作机补齐从 1 开始的 `index` |
| `elements`     | `elements`               | 否       | 省略                                       | 至多 6 项，其中至多 3 项视频主体。混合引用时至多 4 项图片主体                                                |
| `sound`        | `sound`                  | 否       | `true`                                     | 生成同步声音                                                                                                 |

输出固定为 1080p。工作机采用目录和官方样例中的模型 ID。静态 Schema 的默认 ID 带有 `-test` 后缀。`elements` 的 Schema 和模型说明均允许最多 6 项。工作机按模型页示例轮询 `prediction/{id}`，静态 Schema 的旧路径为 `result/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/kwaivgi-kling-video-o3-pro-text-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/kwaivgi-kling-video-o3-pro-text-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/kwaivgi-kling-video-o3-pro-text-to-video.md)

## 分镜与主体参数

- `multi_prompt` 按数组顺序提交。每个镜头的 `prompt` 最多 512 字符，输入时长为 1 至 15 秒，工作机按数组顺序补齐 `index` 并以字符串提交各段 `duration`，各段之和须等于视频总时长。开启多镜头并提供分镜时，分镜优先于顶层提示词。开启多镜头且省略分镜时，Atlas 按提示词自动分镜。
- 使用已有主体时填写 `element_id`，为正的 64 位整数。新建主体填写 `element_name` 和 `reference_type`，可附加 `element_description`。两种标识互斥。
- 新建图片主体使用 `reference_type=image_refer`，填写 `frontal_image` 和 1 至 4 个 `refer_images` URL。新建视频主体使用 `reference_type=video_refer`，填写 1 至 4 个 `refer_videos` URL。当前模型 API 页和 Schema 给出每组最多 4 项，静态模型介绍分别写为 3 张参考图和 1 条参考视频。
- 按主体在数组里的位置使用 `<<<element_1>>>`、`<<<element_2>>>` 等引用，可填写在顶层或分镜提示词中。
- 工作机按已知素材类型校验视频和图片主体数。只填已有主体编号时，Atlas 根据编号确认该主体的素材类型。

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/kwaivgi/kling-video-o3-pro-text-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/kwaivgi/kling-video-o3-pro/text-to-video#usage-examples)

```json
{
  "model": "kwaivgi/kling-video-o3-pro/text-to-video",
  "aspect_ratio": "16:9",
  "duration": 5,
  "multi_shot": true,
  "multi_prompt": [
    {
      "index": 1,
      "prompt": "镜头从工作台的工具缓缓推向 <<<element_1>>>。",
      "duration": "2"
    },
    {
      "index": 2,
      "prompt": "切到侧面近景，展示物体表面的细节。",
      "duration": "3"
    }
  ],
  "elements": [
    {
      "element_name": "桌上木雕",
      "reference_type": "image_refer",
      "frontal_image": "https://example.com/carving-front.jpg",
      "refer_images": ["https://example.com/carving-side.jpg"]
    }
  ],
  "sound": true
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、画面比例、时长和多镜头位于默认区。分镜方案、主体引用及声音位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
