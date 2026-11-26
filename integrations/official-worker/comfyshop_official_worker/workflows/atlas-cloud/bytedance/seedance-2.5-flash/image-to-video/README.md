# Seedance 2.5 Flash 图生视频

Atlas Cloud 模型 ID 为 `bytedance/seedance-2.5-flash/image-to-video`。首帧决定画面起点，尾帧可选。接口定义和请求示例见 Atlas Cloud 的模型页。[官方 API 与输入 Schema](https://www.atlascloud.ai/models/bytedance/seedance-2.5-flash/image-to-video)

## 字段和请求

| ComfyShop 字段       | Atlas 参数          | 必填 | 初始值     | 说明                             |
| -------------------- | ------------------- | ---- | ---------- | -------------------------------- |
| 工作机配置           | `model`             | 是   | 模型 ID    | 从 `execution.config.model` 读取 |
| `first_frame`        | `image`             | 是   | 用户上传   | 首帧图片                         |
| `last_frame`         | `last_image`        | 否   | 空         | 可选的尾帧图片                   |
| `prompt`             | `prompt`            | 否   | 空         | 未填写时使用 Atlas 的默认提示词  |
| `duration_seconds`   | `duration`          | 否   | `5`        | 整数 4 至 30，`-1` 为自动时长    |
| `resolution`         | `resolution`        | 否   | `720p`     | `480p` 或 `720p`                 |
| `aspect_ratio`       | `ratio`             | 否   | `adaptive` | 只接受自适应，保留首帧比例       |
| `generate_audio`     | `generate_audio`    | 否   | `true`     | 生成同步声音                     |
| `add_watermark`      | `watermark`         | 否   | `false`    | 在成品中叠加水印                 |
| `include_last_frame` | `return_last_frame` | 否   | `false`    | 单独交付生成视频的最后一帧图片   |
| `video_format`       | `output_format`     | 否   | `mp4`      | `mp4` 或 `mov`                   |

提示词初始为空。省略 `prompt` 时，Atlas 使用默认提示词 `The scene comes alive with gentle motion and cinematic lighting`。

首帧与尾帧沿用 ComfyShop 的图片上传能力，接收 PNG、JPEG、WebP、GIF。Atlas 要求每边 300–6000 像素、宽高比 0.4–2.5、单张最大 30 MB。工作机使用 `uploadMedia` 换取 URL，分别将两个素材作为单个 URL 写入请求。未提供尾帧时省略 `last_image`。直接调用 Atlas API 时，图片字段也可以使用 Base64 或 Atlas 素材库引用，Atlas 另支持 BMP 和 TIFF。[官方素材上传](https://www.atlascloud.ai/docs/upload-files)

工作机凭 `Authorization: Bearer <API_KEY>` 向 `POST https://api.atlascloud.ai/api/v1/model/generateVideo` 发送 JSON。示例使用首尾帧，返回视频和一张尾帧图片。

```json
{
  "model": "bytedance/seedance-2.5-flash/image-to-video",
  "image": "https://example.com/first-frame.png",
  "last_image": "https://example.com/last-frame.png",
  "prompt": "镜头沿桌面缓慢向前移动，晨光从左侧照入。",
  "duration": 5,
  "resolution": "720p",
  "ratio": "adaptive",
  "generate_audio": true,
  "watermark": false,
  "return_last_frame": true,
  "output_format": "mp4"
}
```

提交后读取 `data.id`，用 `GET /api/v1/model/prediction/{id}` 续查。从完成响应的 `data.outputs` 下载结果。工作流声明视频为主成品，开启尾帧导出时也接收图片。[官方预测文档](https://www.atlascloud.ai/docs/predictions)

## 参数布局与译文

首尾帧、提示词、时长和分辨率在默认区，声音、水印、尾帧导出和视频格式在高级区，固定的自适应比例在隐藏区。工作流标识为 `seedance-25-flash-image-to-video`。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../../docs/deployment.md#官方工作机)
