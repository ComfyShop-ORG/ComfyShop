# Qwen Image 3.0 文生图

根据提示词生成 1 至 4 张图片，可设置尺寸和提示词改写策略。 Atlas Cloud 模型 ID 为 `qwen-image-3.0/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/qwen-image-3.0/text-to-image)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段           | 必填 | 默认值                         | 输入约定                                            |
| -------------------- | ------------------------ | ---- | ------------------------------ | --------------------------------------------------- |
| `model`              | `execution.config.model` | 是   | `qwen-image-3.0/text-to-image` | 工作机从执行配置读取                                |
| `prompt`             | `prompt`                 | 是   | —                              | 非空描述                                            |
| `size`               | `size`                   | 否   | 由模型选择                     | `宽*高`，每边 512 至 2,048 像素。留空省略字段       |
| `n`                  | `image_count`            | 否   | `1`                            | 整数 1 至 4                                         |
| `negative_prompt`    | `negative_prompt`        | 否   | —                              | 希望避免的元素，留空省略字段                        |
| `seed`               | `seed`                   | 否   | 由模型选取                     | 整数 0 至 2,147,483,647                             |
| `prompt_extend`      | `prompt_extend`          | 否   | `true`                         | 智能改写提示词                                      |
| `prompt_extend_mode` | `prompt_extend_mode`     | 否   | `direct`                       | `direct` 单次改写，`agent` 多步改写。启用改写时发送 |

模型说明标注此档位为邀请测试，调用以 Atlas 的账户权限为准。Atlas 样例数据包含 `watermark: false`，水印选项需以 Atlas 发布的端点参数定义为准。

[官方 Schema](https://static.atlascloud.ai/model/schema/qwen-image-3.0-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/qwen-image-3.0-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/qwen-image-3.0-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/qwen-image-3.0/text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/qwen-image-3.0/text-to-image#usage-examples)

```json
{
  "model": "qwen-image-3.0/text-to-image",
  "prompt": "设计飞机博物馆的复古海报，使用干净的几何构图。",
  "size": "1536*1024",
  "n": 2,
  "negative_prompt": "模糊，重影",
  "seed": 42,
  "prompt_extend": true,
  "prompt_extend_mode": "direct"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序下载并保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词、输出尺寸和图片数量。高级参数为负面提示词、随机种子和提示词改写设置。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
