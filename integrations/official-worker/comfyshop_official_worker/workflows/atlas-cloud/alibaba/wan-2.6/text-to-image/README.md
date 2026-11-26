# Wan 2.6 文生图

根据提示词生成图片，可选择尺寸与提示词扩写。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.6/text-to-image`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.6/text-to-image)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段            | 必填 | 默认值                          | 输入约定                                |
| ------------------------- | ------------------------- | ---- | ------------------------------- | --------------------------------------- |
| `model`                   | `execution.config.model`  | 是   | `alibaba/wan-2.6/text-to-image` | 工作机从执行配置读取                    |
| `prompt`                  | `prompt`                  | 是   | 无                              | 描述画面，最多 2,100 字符               |
| `negative_prompt`         | `negative_prompt`         | 否   | 无                              | 描述画面中希望避开的元素，最多 500 字符 |
| `size`                    | `size` 或 `custom_size`   | 否   | `1280*1280`                     | 下列尺寸预设，或自定义宽*高             |
| `enable_prompt_expansion` | `enable_prompt_expansion` | 否   | false                           | 启用提示词优化                          |
| `seed`                    | `seed`                    | 否   | -1                              | 整数，-1 使用随机种子                   |
| `enable_sync_mode`        | `enable_sync_mode`        | 否   | false                           | 等待生成完成                            |
| `enable_base64_output`    | `enable_base64_output`    | 否   | false                           | 返回 Base64 图片                        |

尺寸预设包含 `576*1344`、`720*1280`、`720*1680`、`768*1024`、`800*1200`、`936*2184`、`960*1280`、`960*1440`、`1024*768`、`1024*1024`、`1080*1920`、`1168*1752`、`1200*800`、`1200*1600`、`1224*1632`、`1280*720`、`1280*960`、`1280*1280`、`1344*576`、`1440*960`、`1440*1440`、`1600*1200`、`1632*1224`、`1680*720`、`1752*1168`、`1920*1080`、`2184*936`。自定义尺寸覆盖所选预设。按厂商 API，自定义总像素为 1,638,400 至 2,073,600，长短边比例最多 4:1。Atlas 模型说明确认可设置自定义宽高。[阿里云文生图参数](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/text-to-image-v2-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.6-text-to-image.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.6-text-to-image.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.6-text-to-image.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateImage`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.6-text-to-image/generateImage) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.6/text-to-image#usage-examples)

```json
{
  "model": "alibaba/wan-2.6/text-to-image",
  "prompt": "一张陶瓷花盆的静物照片，光线从左侧窗户照进来，背景是浅灰的墙面。",
  "negative_prompt": "过曝，字幕",
  "size": "1280*1280",
  "enable_prompt_expansion": false,
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存图片，可处理 URL 或 Base64。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词和预设尺寸位于默认区。自定义尺寸、负面提示词、扩写、种子及响应方式位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
