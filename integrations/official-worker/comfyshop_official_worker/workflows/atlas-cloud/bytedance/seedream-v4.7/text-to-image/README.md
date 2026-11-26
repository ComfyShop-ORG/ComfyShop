# Seedream v4.7 文生图

根据提示词生成图片，可选择 1K、2K 或 4K 尺寸预设。Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.7/text-to-image`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/text-to-image)

## 官方参数

| Atlas 参数              | ComfyShop 字段           | 必填 | 默认值                                  | 输入约定                                                                                                  |
| ----------------------- | ------------------------ | ---- | --------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `model`                 | `execution.config.model` | 是   | `bytedance/seedream-v4.7/text-to-image` | 工作机从执行配置读取                                                                                      |
| `prompt`                | `prompt`                 | 是   | 由用户填写                              | 描述主体、构图与风格                                                                                      |
| `size`                  | `image_size`             | 否   | `2048*2048`                             | 从 22 个官方宽高预设中选择。官方要求总像素数介于 921,600 和 16,777,216 之间，宽高比介于 1:16 和 16:1 之间 |
| `prompt_expansion_mode` | `prompt_expansion_mode`  | 否   | `standard`                              | `standard` 优先质量，`fast` 优先速度                                                                      |
| `enable_base64_output`  | `base64_output`          | 否   | `false`                                 | 开启后在预测的 `outputs` 返回 Base64 图像                                                                 |

完整尺寸枚举存放于清单的 `image_size.choices`。默认区展示提示词和图片尺寸，高级区提供扩写模式及 Base64 成品开关。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.7-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.7-text-to-image.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seedream-v4.7/text-to-image",
  "prompt": "玻璃花瓶置于深色窗台，柔和侧光照亮花茎，静物摄影。",
  "size": "2048*2048",
  "prompt_expansion_mode": "standard",
  "enable_base64_output": false
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机下载 `data.outputs` 里的 HTTPS 成品。启用 Base64 时，工作机也可直接解码响应中的图像，再使用相同的成品回传接口保存原图。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/text-to-image#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

维护账号可以通过「编辑参数」调整分组、顺序、标签、说明及默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
