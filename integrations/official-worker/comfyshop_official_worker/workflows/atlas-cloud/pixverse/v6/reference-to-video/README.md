# PixVerse V6 参考图生成视频

用 1 至 7 张参考图片和提示词生成视频，可指定主体或背景。 Atlas Cloud 模型 ID 为 `pixverse/v6/reference-to-video`。[官方模型 API](https://www.atlascloud.ai/models/pixverse/v6/reference-to-video)

## Atlas 接口参数

| Atlas 参数          | ComfyShop 字段                                    | 必填 | 默认值                           | 输入约定                                                  |
| ------------------- | ------------------------------------------------- | ---- | -------------------------------- | --------------------------------------------------------- |
| `model`             | `execution.config.model`                          | 是   | `pixverse/v6/reference-to-video` | 工作机从执行配置读取                                      |
| `prompt`            | `prompt`                                          | 是   | —                                | 非空文字，1 至 5,000 字符，可用 `@名称` 引用图片          |
| `images`            | 参考图槽位 1 至 7                                 | 是   | —                                | 对象数组，至少 1 项，最多 7 项                            |
| `images[].image`    | `reference_image_N` 或 `reference_image_N_source` | 是   | —                                | 上传图片、公开图片 URL、Base64 Data URI 或原始 Base64     |
| `images[].type`     | `reference_type_N`                                | 否   | —                                | `subject` 为主体，`background` 为背景                     |
| `images[].ref_name` | `reference_name_N`                                | 否   | —                                | 引用名称，最多 30 个 UTF-8 字节                           |
| `duration`          | `duration_seconds`                                | 否   | `5`                              | 整数 1 至 15 秒                                           |
| `aspect_ratio`      | `aspect_ratio`                                    | 否   | `16:9`                           | `16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`2:3`、`3:2`、`21:9` |
| `quality`           | `resolution`                                      | 否   | `720p`                           | `360p`、`540p`、`720p`、`1080p`                           |
| `sound`             | `generate_audio`                                  | 否   | `true`                           | 生成同步音频                                              |
| `seed`              | `seed`                                            | 否   | 由 Atlas 选取                    | 整数，留空时省略参数                                      |

参考图接受 PNG、JPEG、WebP。每张图片最多 20 MB，短边至少 300 像素，宽高比为 1:2.5 至 2.5:1。工作机按槽位顺序组装数组，图像和引用信息放在同一对象。Atlas 请求体最多 20 MB，较大的 Base64 图片可改用上传或 URL。

[官方 Schema](https://static.atlascloud.ai/model/schema/pixverse-v6-reference-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/pixverse-v6-reference-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/pixverse-v6-reference-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/pixverse/v6-reference-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/pixverse/v6/reference-to-video#usage-examples)

```json
{
  "model": "pixverse/v6/reference-to-video",
  "prompt": "让 @人物 在 @花园 中缓缓转身。",
  "images": [
    {
      "image": "https://example.com/garden.jpg",
      "type": "background",
      "ref_name": "花园"
    },
    {
      "image": "https://example.com/person.jpg",
      "type": "subject",
      "ref_name": "人物"
    }
  ],
  "duration": 5,
  "aspect_ratio": "16:9",
  "quality": "720p",
  "sound": true
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为前两个参考图上传槽位、提示词、时长、宽高比和分辨率。高级参数包括更多参考图、图片来源、引用类型和名称、同步音频及随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
