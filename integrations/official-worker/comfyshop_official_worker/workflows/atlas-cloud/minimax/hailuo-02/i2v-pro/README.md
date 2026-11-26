# Hailuo 02 Pro 图生视频

从首帧图片生成固定时长的视频，可补充动作描述。 Atlas Cloud 模型 ID 为 `minimax/hailuo-02/i2v-pro`。[官方模型 API](https://www.atlascloud.ai/models/minimax/hailuo-02/i2v-pro)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                        | 必填 | 默认值                      | 输入约定                                         |
| ------------------------- | ------------------------------------- | ---- | --------------------------- | ------------------------------------------------ |
| `model`                   | `execution.config.model`              | 是   | `minimax/hailuo-02/i2v-pro` | 工作机从执行配置读取                             |
| `image`                   | `first_frame` 或 `first_frame_source` | 是   | —                           | JPEG、PNG。上传、公开图片 URL 或 Base64 Data URI |
| `prompt`                  | `prompt`                              | 否   | Schema 提供可编辑示例       | 最多 2,000 字符，可留空                          |
| `enable_prompt_expansion` | `expand_prompt`                       | 否   | `false`                     | 生成前优化提示词                                 |

首帧短边大于 300 像素，宽高比严格介于 2:5 与 5:2 之间，文件不超过 20 MB。Base64 采用 `data:image/jpeg;base64,...` 或 `data:image/png;base64,...`。超出文本容量时可直接上传。Atlas Schema 附有示例图片 URL，首帧来源初始留空，方便直接上传或填写自己的来源。工作机通过已上传图片的元数据校验。官方字段说明指出，开启提示词扩写时还会启用内容检查。时长和分辨率由 Pro 档位决定。

[官方 Schema](https://static.atlascloud.ai/model/schema/minimax-hailuo-02-i2v-pro.json) · [官方示例数据](https://static.atlascloud.ai/model/example/minimax-hailuo-02-i2v-pro.json) · [模型说明](https://static.atlascloud.ai/model/readme/minimax-hailuo-02-i2v-pro.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/minimax/hailuo-02-i2v-pro/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/minimax/hailuo-02/i2v-pro#usage-examples)

```json
{
  "model": "minimax/hailuo-02/i2v-pro",
  "image": "https://example.com/lantern.png",
  "prompt": "灯笼在风中缓缓晃动。",
  "enable_prompt_expansion": false
}
```

从响应取 `id` 或 `data.id`，优先轮询此模型 Schema 的 `GET https://api.atlascloud.ai/api/v1/model/result/{id}`，遇到 404 或 405 时改用通用 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按返回的 `outputs` 或 `output` 数组保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

普通参数为首帧和提示词。高级参数为首帧来源与提示词扩写。工作机读取固定模型 ID。

[工作流清单（含五种语言）](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
