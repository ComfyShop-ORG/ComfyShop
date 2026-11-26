# MiniMax H3-Image 文生图

根据提示词生成 1 至 10 张图片，支持自定义像素尺寸和输出格式。Atlas Cloud 模型 ID 为 `minimax/h3-image/text-to-image`。[模型 API 参考](https://www.atlascloud.ai/models/minimax/h3-image/text-to-image)

## 官方参数

| Atlas 参数                | ComfyShop 字段           | 必填 | 默认值                           | 输入约定                                               |
| ------------------------- | ------------------------ | ---- | -------------------------------- | ------------------------------------------------------ |
| `model`                   | `execution.config.model` | 是   | `minimax/h3-image/text-to-image` | 工作机从执行配置读取                                   |
| `prompt`                  | `prompt`                 | 是   | 由用户填写                       | 1 至 32,000 个字符，描述主体、构图、风格和要渲染的文字 |
| `size`                    | `image_size`             | 否   | `auto`                           | `auto` 或 `宽*高`，保留提交的宽高                      |
| `num_images`              | `image_count`            | 否   | `1`                              | 1 至 10 的整数                                         |
| `enable_prompt_expansion` | `expand_prompt`          | 否   | `true`                           | 生成前优化提示词，自动尺寸要求开启                     |
| `output_format`           | `output_format`          | 否   | `jpeg`                           | `jpeg`、`png` 或 `webp`                                |
| `output_compression`      | `compression_quality`    | 否   | `95`                             | 0 至 100 的 JPEG 或 WebP 质量，PNG 使用无损压缩        |
| `enable_sync_mode`        | `synchronous_response`   | 否   | `false`                          | 提交响应等待并直接包含成品                             |
| `enable_base64_output`    | `base64_output`          | 否   | `false`                          | 启用后工作机解码 Base64 图片并回传原图                 |

自定义宽高每边 468 至 7745 像素，总像素数 655,360 至 20,000,000，宽高比 1:3 至 3:1，均包含边界。`auto` 由提示词扩写选择画面比例，生成 4K 档图片。关闭扩写时使用明确的尺寸，提示词大约前 4,096 个词元生效。[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-h3-image-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-h3-image-text-to-image.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "minimax/h3-image/text-to-image",
  "prompt": "俯拍一只白瓷碟和银色茶匙，漫射日光，简洁的静物摄影。",
  "size": "2048*2048",
  "num_images": 1,
  "enable_prompt_expansion": true,
  "output_format": "jpeg",
  "output_compression": 95,
  "enable_sync_mode": false,
  "enable_base64_output": false
}
```

异步提交后，从 `data.id` 获取编号并轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。同步模式的提交响应可以直接提供 `data.outputs`。工作机在回传前记录编号。租约接管后使用原编号查询成品。[官方调用示例](https://www.atlascloud.ai/models/minimax/h3-image/text-to-image#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、图片尺寸和张数位于默认区，其他设置位于高级区。维护账号可通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
