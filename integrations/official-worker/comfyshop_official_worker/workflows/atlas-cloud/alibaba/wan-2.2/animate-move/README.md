# Wan 2.2 动作迁移

把参考视频里的动作应用到图片人物。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.2/animate-move`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.2/animate-move)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段                                | 必填 | 默认值                         | 输入约定                                                                              |
| ---------- | --------------------------------------------- | ---- | ------------------------------ | ------------------------------------------------------------------------------------- |
| `model`    | `execution.config.model`                      | 是   | `alibaba/wan-2.2/animate-move` | 工作机从执行配置读取                                                                  |
| `image`    | `character_image` 或 `character_image_source` | 是   | 无                             | JPEG、PNG、BMP 或 WebP。宽高各 200 至 4096 像素，长短边比例最多 3:1，最多 5 MB        |
| `video`    | `motion_video` 或 `motion_video_source`       | 是   | 无                             | MP4、MOV 或 AVI。2 至 30 秒，宽高各 200 至 2048 像素，长短边比例最多 3:1，最多 200 MB |
| `mode`     | `mode`                                        | 是   | `wan-pro`                      | `wan-std` 标准模式或 `wan-pro` 专业模式                                               |

图片与参考视频各使用一名正面人物，面部完整可见。上传文件由工作机转换成 Atlas 素材地址。AVI 请使用公开 URL，MP4 和 MOV 支持上传或填写地址。[官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.2-animate-move.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.2-animate-move.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.2-animate-move.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.2-animate-move/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.2/animate-move#usage-examples)

```json
{
  "model": "alibaba/wan-2.2/animate-move",
  "image": "https://example.com/character.png",
  "video": "https://example.com/motion.mp4",
  "mode": "wan-pro"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

人物图、动作视频与模式位于默认区。两个公开地址位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
