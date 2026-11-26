# Vidu Q1 图生视频

使用一张起始图和文字提示生成 5 秒的 1080p 视频。 Atlas Cloud 模型 ID 为 `vidu/q1/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/vidu/q1/image-to-video)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                        | 必填 | 默认值                   | 输入约定                              |
| -------------------- | ------------------------------------- | ---- | ------------------------ | ------------------------------------- |
| `model`              | `execution.config.model`              | 是   | `vidu/q1/image-to-video` | 工作机从执行配置读取                  |
| `image`              | `first_frame` 或 `first_frame_source` | 是   | 无                       | 上传一张图片，或填写一个公开图片 URL  |
| `prompt`             | `prompt`                              | 是   | 无                       | 描述主体、动作和镜头，最多 5,000 字符 |
| `resolution`         | `resolution`                          | 否   | `1080p`                  | 固定 `1080p`                          |
| `duration`           | `duration`                            | 否   | 5                        | 固定 5 秒                             |
| `movement_amplitude` | `movement_amplitude`                  | 否   | `auto`                   | `auto`、`small`、`medium`、`large`    |
| `seed`               | `seed`                                | 否   | 省略                     | 整数，-1 表示随机种子                 |
| `generate_audio`     | `generate_audio`                      | 否   | `true`                   | 是否生成视频音频                      |
| `bgm`                | `bgm`                                 | 否   | `true`                   | 是否添加背景音乐                      |

工作机先将上传图片转换为 Atlas 可接受的素材 URL，再发起生成。留空时省略种子。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-q1-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/vidu-q1-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-q1-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/q1-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/q1/image-to-video#usage-examples)

```json
{
  "model": "vidu/q1/image-to-video",
  "image": "https://example.com/opening.png",
  "prompt": "镜头缓慢推向画面中的钟楼，树叶随风摆动。",
  "duration": 5,
  "resolution": "1080p",
  "movement_amplitude": "auto",
  "generate_audio": true,
  "bgm": true,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图和提示词位于默认区。种子、动作幅度、生成音频、背景音乐及图片来源位于高级区。时长与分辨率为隐藏固定参数。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
