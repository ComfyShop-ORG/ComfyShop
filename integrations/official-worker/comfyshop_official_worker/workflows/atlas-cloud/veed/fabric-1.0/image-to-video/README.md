# VEED Fabric 1.0 图生视频

用一张图片和一段音频生成视频，支持 480p 和 720p。 Atlas Cloud 模型 ID 为 `veed/fabric-1.0/image-to-video`。[官方模型 API](https://www.atlascloud.ai/models/veed/fabric-1.0/image-to-video)

## Atlas 接口参数

| Atlas 参数   | ComfyShop 字段                    | 必填 | 默认值                           | 输入约定                                                             |
| ------------ | --------------------------------- | ---- | -------------------------------- | -------------------------------------------------------------------- |
| `model`      | `execution.config.model`          | 是   | `veed/fabric-1.0/image-to-video` | 工作机从执行配置读取                                                 |
| `image_url`  | `first_frame` 或 `image_source`   | 是   | —                                | JPEG、PNG 或 WebP。上传或填写公开 URL、Base64 数据 URI 或原始 Base64 |
| `audio_url`  | `driving_audio` 或 `audio_source` | 是   | —                                | 1 至 300 秒音频。上传或填写公开 HTTP(S) 地址                         |
| `resolution` | `resolution`                      | 是   | `720p`                           | `480p` 或 `720p`                                                     |

Atlas 规定请求体最多 20 MB。该端点只接收一张图片，图片字段描述中提及的首尾帧比例约束不涉及第二个请求参数。工作机校验上传音频时长，公开地址的音频由 Atlas 校验。

[官方 Schema](https://static.atlascloud.ai/model/schema/veed-fabric-1.0-image-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/veed-fabric-1.0-image-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/veed-fabric-1.0-image-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/veed/fabric-1.0-image-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/veed/fabric-1.0/image-to-video#usage-examples)

```json
{
  "model": "veed/fabric-1.0/image-to-video",
  "image_url": "https://static.atlascloud.ai/media/images/f94672808b8cef8a92bbe3431e4a51b7.jpg",
  "audio_url": "https://static.atlascloud.ai/media/audios/53c4adcf4fa9ce29bf8ec782b756052c.wav",
  "resolution": "720p"
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数包括首帧图片、驱动音频与分辨率。高级参数包括两个素材来源。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
