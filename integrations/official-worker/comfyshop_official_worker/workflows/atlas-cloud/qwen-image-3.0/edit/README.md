# Qwen Image 3.0 图片编辑

按提示词编辑图片，可使用 1 至 3 张参考图。 Atlas Cloud 模型 ID 为 `qwen-image-3.0/edit`。[官方模型 API](https://www.atlascloud.ai/models/qwen-image-3.0/edit)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                                          | 必填 | 默认值                | 输入约定                                                            |
| ---------------------- | ----------------------------------------------------------------------- | ---- | --------------------- | ------------------------------------------------------------------- |
| `model`                | `execution.config.model`                                                | 是   | `qwen-image-3.0/edit` | 工作机从执行配置读取                                                |
| `reference_image_urls` | `reference_image_1` 至 `reference_image_3` 与 `reference_image_sources` | 是   | —                     | 1 至 3 个上传图片、公开 HTTP(S) URL、OSS 临时地址或 Base64 Data URI |
| `prompt`               | `prompt`                                                                | 是   | —                     | 非空编辑要求                                                        |
| `size`                 | `size`                                                                  | 否   | 由模型选择            | `宽*高`，每边 512 至 1,440 像素。留空省略字段                       |
| `n`                    | `image_count`                                                           | 否   | `1`                   | 整数 1 至 4                                                         |
| `negative_prompt`      | `negative_prompt`                                                       | 否   | —                     | 希望避免的元素，留空省略字段                                        |
| `seed`                 | `seed`                                                                  | 否   | 由模型选取            | 整数 0 至 2,147,483,647                                             |
| `prompt_extend`        | `prompt_extend`                                                         | 否   | `true`                | 智能改写提示词                                                      |
| `prompt_extend_mode`   | `prompt_extend_mode`                                                    | 否   | `direct`              | `direct` 单次改写，启用改写时发送                                   |

模型说明标注此档位为邀请测试，调用以 Atlas 的账户权限为准。Atlas 样例数据包含 `watermark: false`，水印选项需以 Atlas 发布的端点参数定义为准。

参考图每张最多 10 MB，建议宽、高 384 至 2,048 像素。支持 JPEG、PNG、WebP、BMP、TIFF 和 GIF。GIF 按首帧处理。工作机先发送上传图片，再按行追加外部引用。OSS 临时地址的访问由 Atlas 处理。[Qwen 原生图像编辑文档](https://www.alibabacloud.com/help/en/model-studio/qwen-image-edit-guide) · [OSS 临时地址说明](https://www.alibabacloud.com/help/en/model-studio/get-temporary-file-url)

[官方 Schema](https://static.atlascloud.ai/model/schema/qwen-image-3.0-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/qwen-image-3.0-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/qwen-image-3.0-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/qwen-image-3.0/edit/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/qwen-image-3.0/edit#usage-examples)

```json
{
  "model": "qwen-image-3.0/edit",
  "reference_image_urls": ["https://example.com/plane.png"],
  "prompt": "保留飞机轮廓，改成线条简洁的博物馆海报。",
  "size": "1440*1024",
  "n": 2,
  "negative_prompt": "模糊，重影",
  "seed": 42,
  "prompt_extend": true,
  "prompt_extend_mode": "direct"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序下载并保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为参考图、提示词、输出尺寸和图片数量。高级参数为参考图来源、负面提示词、随机种子和提示词改写开关。工作机读取隐藏的 `direct` 策略与固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
