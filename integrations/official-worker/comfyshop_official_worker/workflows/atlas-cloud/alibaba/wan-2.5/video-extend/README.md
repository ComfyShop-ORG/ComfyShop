# Wan 2.5 视频续写

根据原视频和提示词续写片段，可提供参考音频。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.5/video-extend`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.5/video-extend)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                      | 必填 | 默认值                         | 输入约定                           |
| ----------------- | ----------------------------------- | ---- | ------------------------------ | ---------------------------------- |
| `model`           | `execution.config.model`            | 是   | `alibaba/wan-2.5/video-extend` | 工作机从执行配置读取               |
| `video`           | `video` 或 `video_source`           | 是   | 无                             | 上传原视频或填写公开 URL           |
| `prompt`          | `prompt`                            | 是   | 无                             | 描述后续画面、动作和声音           |
| `negative_prompt` | `negative_prompt`                   | 否   | 无                             | 描述希望避开的画面元素             |
| `audio`           | `soundtrack` 或 `soundtrack_source` | 否   | 无                             | 上传参考音频或填写公开 URL         |
| `resolution`      | `resolution`                        | 否   | `720p`                         | `480p`、`720p` 或 `1080p`          |
| `duration`        | `duration`                          | 否   | 5                              | `5`、`6`、`7`、`8`、`9` 或 `10` 秒 |
| `seed`            | `seed`                              | 否   | -1                             | 整数，-1 使用随机种子              |

工作机将上传素材转换成 Atlas 地址，Atlas 校验源文件的媒体格式。`enable_prompt_expansion` 出现在静态 Schema 的字段排序里，当前请求属性和调用示例采用已列出的参数。工作机按调用示例使用 `prediction/{id}`。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.5-video-extend.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.5-video-extend.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.5-video-extend.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.5-video-extend/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.5/video-extend#usage-examples)

```json
{
  "model": "alibaba/wan-2.5/video-extend",
  "video": "https://example.com/riverwalk.mp4",
  "prompt": "镜头继续沿河边移动，拐过石桥，露出夜色里的街灯。",
  "audio": "https://example.com/river.wav",
  "resolution": "720p",
  "duration": 6,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

原视频、提示词、分辨率与时长位于默认区。素材地址、负面提示词、音频与种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
