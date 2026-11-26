# Wan 2.6 图像编辑

根据提示词编辑一至四张图片，可指定尺寸与扩写设置。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.6/image-edit`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.6/image-edit)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                                      | 必填 | 默认值                       | 输入约定                                                                                           |
| ------------------------- | --------------------------------------------------- | ---- | ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`                            | 是   | `alibaba/wan-2.6/image-edit` | 工作机从执行配置读取                                                                               |
| `prompt`                  | `prompt`                                            | 是   | 无                           | 描述要保留和修改的元素，最多 2,000 字符                                                            |
| `negative_prompt`         | `negative_prompt`                                   | 否   | 无                           | 描述希望避免的元素，最多 500 字符                                                                  |
| `images`                  | `reference_1` 至 `reference_4`、`reference_sources` | 是   | 无                           | 一至四个公开图片 URL。JPEG、无透明通道的 PNG、BMP 或 WebP，宽高各 384 至 5000 像素，每张最多 10 MB |
| `size`                    | `size` 或 `custom_size`                             | 否   | `1280*1280`                  | 使用端点预设或自定义宽*高                                                                          |
| `enable_prompt_expansion` | `enable_prompt_expansion`                           | 否   | false                        | 启用提示词优化                                                                                     |
| `seed`                    | `seed`                                              | 否   | -1                           | 整数，-1 使用随机种子                                                                              |
| `enable_sync_mode`        | `enable_sync_mode`                                  | 否   | false                        | 等待生成完成                                                                                       |
| `enable_base64_output`    | `enable_base64_output`                              | 否   | false                        | 返回 Base64 图片                                                                                   |

工作机将上传图片转换为素材地址，并追加用户填入的公开 URL。自定义尺寸覆盖预设，按厂商编辑接口的总像素范围 589,824 至 4,194,304 和长短边比例上限 4:1 校验。Atlas 端点的 24 个尺寸预设与模型说明中的尺寸示例分别见以下文档。[阿里云编辑参数](https://www.alibabacloud.com/help/en/model-studio/wan-image-generation-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.6-image-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.6-image-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.6-image-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.6-image-edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.6/image-edit#usage-examples)

```json
{
  "model": "alibaba/wan-2.6/image-edit",
  "prompt": "把参考图中陶瓷器皿的釉面改为哑光天蓝，保留造型、背景和光照。",
  "images": ["https://example.com/ceramic.jpg"],
  "size": "1280*1280",
  "enable_prompt_expansion": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、第一张参考图和尺寸位于默认区。其他图片、公开地址、自定义尺寸、负面提示词、扩写、种子和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
