# Vidu 2.0 参考生视频

用一至三张图片作为视频参考，保持主体外观一致。 Atlas Cloud 模型 ID 为 `vidu/reference-to-video-2.0`。[官方模型 API](https://www.atlascloud.ai/models/vidu/reference-to-video-2.0)

## Atlas 接口参数

| Atlas 参数           | ComfyShop 字段                                              | 必填 | 默认值                        | 输入约定                                                                                  |
| -------------------- | ----------------------------------------------------------- | ---- | ----------------------------- | ----------------------------------------------------------------------------------------- |
| `model`              | `execution.config.model`                                    | 是   | `vidu/reference-to-video-2.0` | 工作机从执行配置读取                                                                      |
| `images`             | `reference_image_1` 至 `reference_image_3`、`image_sources` | 是   | 官方示例图                    | 1 至 3 张 JPEG、PNG 或 WebP，每张最多 50 MB，每边至少 128 像素，宽高比大于 1:4 且小于 4:1 |
| `prompt`             | `prompt`                                                    | 是   | 官方示例                      | 最多 1,500 字符                                                                           |
| `aspect_ratio`       | `aspect_ratio`                                              | 否   | `16:9`                        | `16:9`、`9:16`、`1:1`                                                                     |
| `movement_amplitude` | `movement_amplitude`                                        | 否   | `auto`                        | `auto`、`small`、`medium`、`large`                                                        |
| `seed`               | `seed`                                                      | 否   | 0                             | 整数，0 表示随机种子                                                                      |

可上传图片或逐行填写公开 URL、带媒体类型的 Base64 数据网址。提交顺序为上传栏位，再追加逐行填写的来源。ComfyShop 的来源字段限制为 4 MiB。Atlas 公布的默认示例图见请求示例。模型页面演示 `prediction` 轮询路径，静态 Schema 也列出旧的 `result` 路径。 [官方 Schema](https://static.atlascloud.ai/model/schema/vidu-reference-to-video-2.0.json) · [模型说明](https://static.atlascloud.ai/model/readme/vidu-reference-to-video-2.0.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/vidu/reference-to-video-2.0/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/vidu/reference-to-video-2.0#usage-examples)

```json
{
  "model": "vidu/reference-to-video-2.0",
  "images": [
    "https://static.atlascloud.ai/media/images/1745492230971199265_J3J5tO7p.jpg",
    "https://static.atlascloud.ai/media/images/1745492247387641003_Z3jDAxur.jpg"
  ],
  "prompt": "画中的女孩走进房间，把手中的杯子放到桌上。",
  "aspect_ratio": "16:9",
  "movement_amplitude": "auto",
  "seed": 0
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

首张参考图、提示词、画面比例和动作幅度在默认区。更多参考图、图片来源和种子在高级区。 [工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../docs/deployment.md#官方工作机)
