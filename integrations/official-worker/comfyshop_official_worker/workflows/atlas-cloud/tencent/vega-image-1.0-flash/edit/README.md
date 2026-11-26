# 腾讯 Vega 1.0 Flash 图像编辑

根据主参考图、编辑指令和最多五张补充参考图生成一张图像。 Atlas Cloud 模型 ID 为 `tencent/vega-image-1.0-flash/edit`。[官方模型 API](https://www.atlascloud.ai/models/tencent/vega-image-1.0-flash/edit)

## Atlas 接口参数

| Atlas 参数        | ComfyShop 字段                                              | 必填 | 默认值                              | 输入约定                                             |
| ----------------- | ----------------------------------------------------------- | ---- | ----------------------------------- | ---------------------------------------------------- |
| `model`           | `execution.config.model`                                    | 是   | `tencent/vega-image-1.0-flash/edit` | 工作机从执行配置读取                                 |
| `image`           | `primary_image` 或 `primary_image_source`                   | 是   | 无                                  | 一张主参考图，上传、公开 URL 或 Base64               |
| `images`          | `reference_image_1` 至 `reference_image_5`、`image_sources` | 否   | 省略                                | 最多五张补充参考图，上传、公开 URL 或 Base64         |
| `prompt`          | `prompt`                                                    | 是   | 官方示例                            | 描述要应用的修改，至少 1 个字符                      |
| `size`            | `size`                                                      | 否   | `1K`                                | `1K`、`2K`、`4K`，Atlas 也接受 `resolution` 作为别名 |
| `aspect_ratio`    | `aspect_ratio`                                              | 否   | `1:1`                               | `16:9`、`9:16`、`1:1`、`3:4`、`4:3`                  |
| `negative_prompt` | `negative_prompt`                                           | 否   | 省略                                | 描述画面中希望避开的内容                             |
| `enhance_prompt`  | `enhance_prompt`                                            | 否   | `false`                             | 是否增强提示词                                       |
| `seed`            | `seed`                                                      | 否   | 省略                                | 整数随机种子                                         |
| `input_region`    | `input_region`                                              | 否   | `Oversea`                           | `Mainland`、`Oversea`、`OverseaUSWest`，用于内容审核 |

参考图使用 JPEG、PNG 或 WebP，适用于非真人素材。上传图先转换为素材 URL，补充图按上传栏位和随后填写的来源排序。接受纯 Base64 和带媒体类型的数据网址。Atlas 的内联图片解码后合计上限为 7 MB。ComfyShop 的两个来源字段各限制为 4 MiB，Base64 解码后合计在该上限以内。[腾讯云点播输入文件说明](https://cloud.tencent.com/document/product/266/31773)

[官方 Schema](https://static.atlascloud.ai/model/schema/tencent-vega-image-1.0-flash-edit.json) · [官方示例数据](https://static.atlascloud.ai/model/example/tencent-vega-image-1.0-flash-edit.json) · [模型说明](https://static.atlascloud.ai/model/readme/tencent-vega-image-1.0-flash-edit.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方调用示例](https://www.atlascloud.ai/models/tencent/vega-image-1.0-flash/edit#usage-examples)

```json
{
  "model": "tencent/vega-image-1.0-flash/edit",
  "image": "https://example.com/desk.png",
  "images": ["https://example.com/lamp.png"],
  "prompt": "换成干净的浅灰背景，把参考图中的台灯放在桌面左侧。",
  "size": "1K",
  "aspect_ratio": "1:1",
  "enhance_prompt": false,
  "input_region": "Oversea"
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

主参考图、编辑指令、分辨率和画面比例位于默认区。补充图、图片来源、反向提示词、提示词增强、种子和输入地区位于高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
