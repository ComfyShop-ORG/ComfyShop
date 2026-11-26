# Seedream v4.7 组图编辑

Atlas Cloud 模型 ID 为 `bytedance/seedream-v4.7/edit-sequential`。请求字段见官方 Schema。提交和轮询路径采用模型 API 选项卡的调用示例。[官方 API 页](https://www.atlascloud.ai/zh/models/bytedance/seedream-v4.7/edit-sequential?tab=api) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4.7-edit-sequential.json)

## 字段和请求

| ComfyShop 字段                  | Atlas 参数              | 初始值      | 说明                                           |
| ------------------------------- | ----------------------- | ----------- | ---------------------------------------------- |
| `prompt`                        | `prompt`                | 用户填写    | 描述要对参考图做的编辑                         |
| `reference_1` 至 `reference_10` | `images`                | 用户上传    | 1 至 10 张，按素材编号顺序提交                 |
| `image_count`                   | `num_images`            | `2`         | 生成张数上限为 1 至 14，与参考图合计最多 15 张 |
| `image_size`                    | `size`                  | `2048*2048` | 选择官方提供的尺寸枚举                         |
| `prompt_expansion_mode`         | `prompt_expansion_mode` | `standard`  | `standard` 优先质量，`fast` 优先速度           |

工作流使用通用素材映射。工作机通过 `POST /api/v1/model/uploadMedia` 上传参考图，将各槽位的返回 URL 依编号写入 `images`，再向 `POST https://api.atlascloud.ai/api/v1/model/generateImage` 提交。工作机固定使用 URL 交付，将 `enable_base64_output` 设为 `false`。请求使用 `Authorization: Bearer <API_KEY>`。[素材上传 API](https://www.atlascloud.ai/docs/en/upload-files)

```json
{
  "model": "bytedance/seedream-v4.7/edit-sequential",
  "prompt": "保留主体构图，为两张成品使用不同的背景色。",
  "images": ["https://example.com/reference.png"],
  "num_images": 2,
  "size": "2048*2048",
  "prompt_expansion_mode": "standard",
  "enable_base64_output": false
}
```

从提交响应读取 `data.id` 后，轮询 `GET /api/v1/model/prediction/{id}`。生成完成后按 `data.outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/en/predictions)

## 参数布局与译文

默认区显示提示词、前两个参考图槽位、生成张数和图片尺寸。其余参考图槽位和扩写模式在高级区。工作流标识为 `seedream-v47-edit-sequential`，维护账号可在「编辑参数」保存当前版本的布局。[工作流清单与五种译文](workflow.json) · [同步命令](../../../../../../../../docs/deployment.md#官方工作机)
