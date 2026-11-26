# MiniMax H3-Image Highspeed 图片编辑

根据文字和 1 至 16 张参考图生成 1 至 10 张结果。可用参考图指定主体、材质、色彩或构图。Atlas Cloud 模型 ID 为 `minimax/h3-image-highspeed/edit`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-image-highspeed/edit)

## 官方参数

| Atlas 参数             | ComfyShop 字段                  | 必填 | 默认值                            | 输入约定                                                 |
| ---------------------- | ------------------------------- | ---- | --------------------------------- | -------------------------------------------------------- |
| `model`                | `execution.config.model`        | 是   | `minimax/h3-image-highspeed/edit` | 工作机从执行配置读取                                     |
| `prompt`               | `prompt`                        | 是   | 由用户填写                        | 1 至 32,000 个字符，描述要修改和保留的内容。模型自动扩写 |
| `reference_images`     | `reference_1` 至 `reference_16` | 是   | 由用户上传                        | 1 至 16 张，按槽位编号组装，跳过空槽                     |
| `size`                 | `image_size`                    | 否   | `auto`                            | 自动选择比例，或填写 `宽*高`                             |
| `num_images`           | `image_count`                   | 否   | `1`                               | 1 至 10 的整数                                           |
| `output_format`        | `output_format`                 | 否   | `jpeg`                            | `jpeg`、`png` 或 `webp`                                  |
| `output_compression`   | `compression_quality`           | 否   | `95`                              | 0 至 100 的 JPEG 或 WebP 画质，PNG 使用无损压缩          |
| `enable_sync_mode`     | `synchronous_response`          | 否   | `false`                           | 提交响应等待并直接包含成品                               |
| `enable_base64_output` | `base64_output`                 | 否   | `false`                           | 开启后工作机解码 Base64 图像并回传原图                   |

ComfyShop 可上传 PNG、JPEG 和 WebP。参考图单张最多 64 MB，每边 128 至 8192 像素，长边最多为短边的 4 倍。工作机先校验素材，再使用上传返回的 URL。直接调用 Atlas API 时，还可使用 HEIC、HEIF 和 Base64。提示词可按提交数组的顺序引用图片。[素材上传](https://www.atlascloud.ai/docs/upload-files)

输出尺寸 `auto` 根据参考图和提示词选择画面比例，生成 4K 档图片。自定义尺寸每边 468 至 7745 像素，总像素数 655,360 至 20,000,000，宽高比 1:3 至 3:1，均包含边界。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-image-highspeed-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-image-highspeed-edit.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。参考图地址为示例。

```json
{
  "model": "minimax/h3-image-highspeed/edit",
  "prompt": "保留第一张图中的手提包，采用第二张图的光线和背景。",
  "reference_images": ["https://example.com/bag.png", "https://example.com/studio.png"],
  "size": "auto",
  "num_images": 1,
  "output_format": "jpeg",
  "output_compression": 95,
  "enable_sync_mode": false,
  "enable_base64_output": false
}
```

异步模式从 `data.id` 取得编号后轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。同步模式可直接读取提交响应的 `data.outputs`。工作机记录编号后回传成品。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-image-highspeed/edit#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、前两个参考图、尺寸与张数位于默认区，其余参考图及输出设置位于高级区。维护账号可通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
