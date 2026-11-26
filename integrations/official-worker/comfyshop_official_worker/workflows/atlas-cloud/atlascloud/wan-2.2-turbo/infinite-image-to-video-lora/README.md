# Atlas Cloud Wan 2.2 Turbo 无限图生视频 LoRA

从起始图生成连续的 5 秒片段，可分别使用高噪声和低噪声 LoRA 权重。 Atlas Cloud 模型 ID 为 `atlascloud/wan-2.2-turbo/infinite-image-to-video-lora`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/infinite-image-to-video-lora)

## Atlas 接口参数

| Atlas 参数         | ComfyShop 字段                        | 必填 | 默认值                                                  | 输入约定                                                            |
| ------------------ | ------------------------------------- | ---- | ------------------------------------------------------- | ------------------------------------------------------------------- |
| `model`            | `execution.config.model`              | 是   | `atlascloud/wan-2.2-turbo/infinite-image-to-video-lora` | 工作机从执行配置读取                                                |
| `image`            | `first_frame` 或 `first_frame_source` | 是   | 无                                                      | 上传起始图，或填写公开 URL、Base64 数据网址                         |
| `prompt`           | `prompt`                              | 是   | 官方示例                                                | 每行一个片段，工作机按行转为 1 至 6 项的 `string[]`，跳过空行       |
| `resolution`       | `resolution`                          | 否   | `720p`                                                  | `480p`、`720p` 或 `1080p`，后处理为每秒 30 帧                       |
| `duration`         | `duration`                            | 否   | 5                                                       | 每段固定 5 秒，合计 5 至 30 秒                                      |
| `seed`             | `seed`                                | 否   | -1                                                      | 整数，-1 使用随机种子                                               |
| `high_noise_loras` | `high_noise_loras`                    | 否   | `[]`                                                    | 高噪声权重数组。每项必填字符串 `path`，选填有限数值 `scale`，默认 1 |
| `low_noise_loras`  | `low_noise_loras`                     | 否   | `[]`                                                    | 低噪声权重数组。每项必填字符串 `path`，选填有限数值 `scale`，默认 1 |
| `loras`            | `loras`                               | 否   | `[]`                                                    | 通用 LoRA 数组，接口保留开放的元素结构                              |

权重需要使用与 Wan 2.2 14B 对应的单个 `.safetensors` 文件。示例中的图片和权重 URL 为占位地址。表单保留 Schema 中可编辑的英文例句。[官方 LoRA 指南](https://www.atlascloud.ai/docs/en/models/lora) · [官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-wan-2.2-turbo-infinite-image-to-video-lora.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-wan-2.2-turbo-infinite-image-to-video-lora.json) · [模型说明](https://static.atlascloud.ai/model/readme/atlascloud-wan-2.2-turbo-infinite-image-to-video-lora.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/wan-2.2-turbo-infinite-image-to-video-lora/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/wan-2.2-turbo/infinite-image-to-video-lora#usage-examples)

```json
{
  "model": "atlascloud/wan-2.2-turbo/infinite-image-to-video-lora",
  "image": "https://example.com/cat.png",
  "prompt": ["小猫走进草地，镜头缓慢跟随。", "小猫抬头观察，镜头从侧面推近。"],
  "duration": 5,
  "resolution": "720p",
  "seed": -1,
  "high_noise_loras": [
    {
      "path": "https://example.com/wan-2.2-high-noise.safetensors",
      "scale": 1
    }
  ],
  "low_noise_loras": [
    {
      "path": "https://example.com/wan-2.2-low-noise.safetensors"
    }
  ],
  "loras": []
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

起始图、分段提示词和分辨率位于默认区。图片来源、种子和三组 LoRA 位于高级区。工作机提交隐藏的固定单段时长。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
