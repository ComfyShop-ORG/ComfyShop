# Seedream v4 连续图像编辑

从提示词和可选参考图生成一组关联图像，可自定义尺寸。 Atlas Cloud 模型 ID 为 `bytedance/seedream-v4/edit-sequential`。[官方模型 API](https://www.atlascloud.ai/models/bytedance/seedream-v4/edit-sequential)

## Atlas 接口参数

| Atlas 参数             | ComfyShop 字段                                       | 必填 | 默认值                                  | 输入约定                                                     |
| ---------------------- | ---------------------------------------------------- | ---- | --------------------------------------- | ------------------------------------------------------------ |
| `model`                | `execution.config.model`                             | 是   | `bytedance/seedream-v4/edit-sequential` | 工作机从执行配置读取                                         |
| `prompt`               | `prompt`                                             | 是   | 无                                      | 描述整组内容和需要编辑的部分                                 |
| `images`               | `reference_1` 至 `reference_10`、`reference_sources` | 否   | 无                                      | 省略时只用提示词。提供时为 1 至 10 个 URL 或 Base64 data URL |
| `size`                 | `size`                                               | 否   | `2048*2048`                             | `宽*高` 像素格式，每边 1024 至 4096                          |
| `max_images`           | `max_images`                                         | 否   | 1                                       | 整数 1 至 14，指定成品张数                                   |
| `enable_base64_output` | `enable_base64_output`                               | 否   | false                                   | 开启后返回 Base64 图片，工作机解码保存                       |

上传文件按编号提交，然后提交文本区按行填写的公开 HTTP(S) 地址或 Base64 data URL。文本字段上限为 4 MiB。BytePlus 模型文档说明参考图与实际成品合计最多 15 张。静态示例含 `enable_sync_mode`，请求字段采用 Atlas 端点文档定义。[BytePlus 图像 API](https://docs.byteplus.com/en/docs/modelark/image-generation-api) · [官方 Schema](https://static.atlascloud.ai/model/schema/bytedance-seedream-v4-edit-sequential.json) · [官方示例数据](https://static.atlascloud.ai/model/example/bytedance-seedream-v4-edit-sequential.json) · [模型说明](https://static.atlascloud.ai/model/readme/bytedance-seedream-v4-edit-sequential.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。将示例地址替换为实际参考图。[官方端点文档](https://www.atlascloud.ai/docs/more-models/bytedance/seedream-v4-edit-sequential/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/bytedance/seedream-v4/edit-sequential#usage-examples)

```json
{
  "model": "bytedance/seedream-v4/edit-sequential",
  "prompt": "根据参考图制作三张同一花瓶的插图，分别放在清晨窗台、阴天书桌和夜晚柜台，保留器形。",
  "images": ["https://example.com/vase.png"],
  "size": "2048*1536",
  "max_images": 3
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首张参考图、尺寸和最多生成张数位于默认区。其余参考图、素材地址和 Base64 输出位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
