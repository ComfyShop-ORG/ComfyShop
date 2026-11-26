# Nano Banana 2 Developer 图像编辑

按提示词修改或融合参考图，可调节分辨率、思考档位及网页搜索。 Atlas Cloud 模型 ID 为 `google/nano-banana-2/edit-developer`。[官方模型 API](https://www.atlascloud.ai/models/google/nano-banana-2/edit-developer)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                                | 输入约定                           |
| ---------------------- | ---------------------------------------------------- | ---- | ------------------------------------- | ---------------------------------- |
| `model`                | `execution.config.model`                             | 是   | `google/nano-banana-2/edit-developer` | 工作机从执行配置读取               |
| `prompt`               | `prompt`                                             | 是   | 无                                    | 描述要修改和保留的部分             |
| `images`               | `reference_1` 至 `reference_14`、`reference_sources` | 是   | 无                                    | 1 至 14 个公开的 HTTP(S) 图片地址  |
| `aspect_ratio`         | `aspect_ratio`                                       | 否   | 由模型决定                            | Schema 的 10 个比例预设            |
| `resolution`           | `resolution`                                         | 否   | `1k`                                  | `1k`、`2k` 或 `4k`                 |
| `thinking_level`       | `thinking_level`                                     | 否   | `default`                             | `default`、`high` 或 `minimal`     |
| `enable_web_search`    | `enable_web_search`                                  | 否   | false                                 | 使用 Google 网页搜索补充实时信息   |
| `top_p`                | `top_p`                                              | 否   | 0.95                                  | 数值 0 至 1                        |
| `temperature`          | `temperature`                                        | 否   | 1                                     | 数值 0 至 1                        |
| `seed`                 | `seed`                                               | 否   | -1                                    | 整数。-1 使用随机种子              |
| `enable_sync_mode`     | `enable_sync_mode`                                   | 否   | false                                 | 等待完成后从提交响应取结果         |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                 | 返回 Base64 图片，由工作机解码保存 |

工作机将上传的图片转成素材地址，再按行追加用户填写的公开图片地址。比例选择模型默认时，工作机省略 `aspect_ratio`。静态示例含 `output_format`，本接口的请求 Schema 列出上表字段。[官方 Schema](https://static.atlascloud.ai/model/schema/google-nano-banana-2-edit-developer.json) · [官方示例数据](https://static.atlascloud.ai/model/example/google-nano-banana-2-edit-developer.json) · [模型说明](https://static.atlascloud.ai/model/readme/google-nano-banana-2-edit-developer.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/google/nano-banana-2/edit-developer#usage-examples)

```json
{
  "model": "google/nano-banana-2/edit-developer",
  "prompt": "保留旧钟的轮廓和刻度，改用冷色光线，并将背景换成磨砂蓝灰色。",
  "images": ["https://example.com/clock.jpg"],
  "aspect_ratio": "3:4",
  "resolution": "2k",
  "thinking_level": "high"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、比例及分辨率位于默认区。其余参考图、素材地址、思考、搜索、采样和响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
