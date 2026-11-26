# Qwen Image 2.0 文生图

根据中文或英文提示词生成图片，可指定尺寸和随机种子。 Atlas Cloud 模型 ID 为 `qwen/qwen-image-2.0/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/qwen/qwen-image-2.0/text-to-image)

## Atlas 接口参数

| Atlas 参数 | ComfyShop 字段           | 必填 | 默认值                              | 输入约定                                          |
| ---------- | ------------------------ | ---- | ----------------------------------- | ------------------------------------------------- |
| `model`    | `execution.config.model` | 是   | `qwen/qwen-image-2.0/text-to-image` | 工作机从执行配置读取                              |
| `prompt`   | `prompt`                 | 是   | —                                   | 中文或英文，最多 800 字符                         |
| `size`     | `size`                   | 否   | `1024*1024`                         | `宽*高`，每边 512 至 2,048 像素                   |
| `seed`     | `seed`                   | 否   | `-1`                                | `-1` 为随机。固定种子为 0 至 2,147,483,647 的整数 |

工作机把宽高作为 `size` 字符串发送并校验每边像素。

[官方 Schema](https://static.atlascloud.ai/model/schema/qwen-qwen-image-2.0-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/qwen-qwen-image-2.0-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/qwen-qwen-image-2.0-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/qwen/qwen-image-2.0-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/qwen/qwen-image-2.0/text-to-image#usage-examples)

```json
{
  "model": "qwen/qwen-image-2.0/text-to-image",
  "prompt": "柔和的光线照亮浅色花瓣，浅绿色背景。",
  "size": "1024*1024",
  "seed": -1
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按返回的 `outputs` 或 `output` 下载并保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为提示词和输出尺寸。高级参数为随机种子。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
