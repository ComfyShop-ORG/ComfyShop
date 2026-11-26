# Seedream v4.7 图片编辑

按文字指令编辑参考图。每次可提供 1 至 10 张参考图。Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.7/edit`。[模型 API 参考](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/edit)

## 官方参数

| Atlas 参数              | ComfyShop 字段                  | 必填 | 默认值                         | 输入约定                                                                     |
| ----------------------- | ------------------------------- | ---- | ------------------------------ | ---------------------------------------------------------------------------- |
| `model`                 | `execution.config.model`        | 是   | `bytedance/seedream-v4.7/edit` | 工作机从执行配置读取                                                         |
| `prompt`                | `prompt`                        | 是   | 由用户填写                     | 描述要做的编辑，可按顺序引用图片                                             |
| `images`                | `reference_1` 至 `reference_10` | 是   | 由用户上传                     | 1 至 10 张，按槽位编号组成数组，跳过空槽                                     |
| `size`                  | `image_size`                    | 否   | `2048*2048`                    | 22 个 1K、2K 和 4K 预设，宽高比 1:16 至 16:1，总像素数 921,600 至 16,777,216 |
| `prompt_expansion_mode` | `prompt_expansion_mode`         | 否   | `standard`                     | `standard` 优先质量，`fast` 优先速度                                         |
| `enable_base64_output`  | `base64_output`                 | 否   | `false`                        | 开启后工作机解码图像再回传原件                                               |

ComfyShop 参考图支持 PNG、JPEG、WebP 和 GIF。工作机先上传参考图，再把返回的 URL 写入 `images`。直接调用 Atlas API 时也可提供 Base64。[官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.7-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4.7-edit.json) · [素材上传](https://www.atlascloud.ai/docs/upload-files)

## API 调用

将下列 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`，使用 `Authorization: Bearer <API_KEY>`。参考图地址为示例。

```json
{
  "model": "bytedance/seedream-v4.7/edit",
  "prompt": "把第一张图的桌面改成第二张图中的浅色木纹，保留原来的光影。",
  "images": ["https://example.com/room.png", "https://example.com/wood.png"],
  "size": "2048*2048",
  "prompt_expansion_mode": "standard",
  "enable_base64_output": false
}
```

从响应读取 `data.id` 并轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。成品由 `data.outputs` 返回。[官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4.7/edit#usage-examples) · [预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、图片尺寸与前两个参考图位于默认区。其余参考图、扩写模式和 Base64 成品开关位于高级区。维护账号可以通过「编辑参数」调整布局、说明和默认值。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
