# Seedream v4.7 文生组图

用一份提示词生成风格一致的组图，适合故事分镜和系列图片。Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.7/sequential`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/sequential)

## 官方参数

| Atlas 参数              | ComfyShop 字段           | 必填 | 默认值                               | 输入约定                                                                     |
| ----------------------- | ------------------------ | ---- | ------------------------------------ | ---------------------------------------------------------------------------- |
| `model`                 | `execution.config.model` | 是   | `bytedance/seedream-v4.7/sequential` | 工作机从执行配置读取                                                         |
| `prompt`                | `prompt`                 | 是   | 由用户填写                           | 描述组图的主题、张数和每张内容                                               |
| `num_images`            | `image_count`            | 否   | `1`                                  | 1 至 14 的整数，表示生成张数上限                                             |
| `size`                  | `image_size`             | 否   | `2048*2048`                          | 22 个 1K、2K 和 4K 预设，宽高比 1:16 至 16:1，总像素数 921,600 至 16,777,216 |
| `prompt_expansion_mode` | `prompt_expansion_mode`  | 否   | `standard`                           | `standard` 优先质量，`fast` 优先速度                                         |
| `enable_base64_output`  | `base64_output`          | 否   | `false`                              | 开启后工作机解码 Base64 图像并保存原件                                       |

提示词中需要的张数应在所选上限以内。实际张数由模型根据提示词决定，所有返回图片按响应顺序保存。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.7-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.7-sequential.json)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。

```json
{
  "model": "bytedance/seedream-v4.7/sequential",
  "prompt": "用一致的木刻插画风格绘制两张图。第一张是晨雾中的灯塔，第二张是黄昏中的同一座灯塔。",
  "num_images": 2,
  "size": "2048*2048",
  "prompt_expansion_mode": "standard",
  "enable_base64_output": false
}
```

从响应读取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`，从 `data.outputs` 获取组图。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/sequential#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

默认区包含提示词、张数上限和图片尺寸，高级区包含扩写模式及 Base64 成品开关。维护账号可通过「编辑参数」调整布局、说明与默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
