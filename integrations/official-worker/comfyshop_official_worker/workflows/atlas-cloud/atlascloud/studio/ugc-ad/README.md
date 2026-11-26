# Atlas Cloud Studio UGC 短视频广告

从商品图生成创作者口播、使用前后对比或开箱短视频。 Atlas Cloud 模型 ID 为 `atlascloud/studio/ugc-ad`。[官方模型 API](https://www.atlascloud.ai/models/atlascloud/studio/ugc-ad)

## Atlas 接口参数

| Atlas 参数       | ComfyShop 字段                      | 必填 | 默认值                     | 输入约定                                                                              |
| ---------------- | ----------------------------------- | ---- | -------------------------- | ------------------------------------------------------------------------------------- |
| `model`          | `execution.config.model`            | 是   | `atlascloud/studio/ugc-ad` | 工作机从执行配置读取                                                                  |
| `product_image`  | `product_image` 或 `product_source` | 是   | 无                         | 商品图上传最多 10 MB，也可提供公开图片 URL                                            |
| `model_image`    | `model_image` 或 `model_source`     | 否   | 省略                       | 达人或模特图上传最多 10 MB，也可提供公开图片 URL                                      |
| `user_prompt`    | `user_prompt`                       | 是   | 无                         | 描述商品卖点、品牌调性或拍摄要求                                                      |
| `ad_type`        | `ad_type`                           | 否   | `creator_recommendation`   | `creator_recommendation` 创作者口播、`before_after` 使用前后对比、`unboxing` 开箱分享 |
| `duration`       | `duration`                          | 否   | 10                         | 4 至 15 秒，整数枚举                                                                  |
| `ratio`          | `ratio`                             | 否   | `9:16`                     | `1:1`、`3:4`、`4:3`、`16:9`、`9:16`                                                   |
| `resolution`     | `resolution`                        | 否   | `720p`                     | `480p`、`720p`、`1080p`、`720p-esr`、`1080p-esr`、`1440p-esr`、`4k-esr`               |
| `generate_audio` | `generate_audio`                    | 否   | `yes`                      | `yes` 生成口播人声及环境声，`no` 静音                                                 |
| `count`          | `count`                             | 否   | 1                          | `1` 或 `2` 条                                                                         |

上传的商品图和达人图分别转换为单个 URL。`generate_audio` 提交字符串枚举。官方静态样例缺少商品图，下面的调用按当前请求 Schema 补齐。[官方 Schema](https://static.atlascloud.ai/model/schema/atlascloud-studio-ugc-ad.json) · [官方示例数据](https://static.atlascloud.ai/model/example/atlascloud-studio-ugc-ad-v2.json) · [模型说明](https://www.atlascloud.ai/workflow/wf-ugc-ad)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/atlascloud/studio-ugc-ad/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/atlascloud/studio/ugc-ad#usage-examples)

```json
{
  "model": "atlascloud/studio/ugc-ad",
  "product_image": "https://example.com/travel-mug.png",
  "user_prompt": "展示旅行杯的开箱过程，特写杯盖结构和杯身材质。",
  "ad_type": "unboxing",
  "duration": 10,
  "ratio": "9:16",
  "resolution": "720p",
  "generate_audio": "yes",
  "count": 1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

商品图、达人图、创作指令、广告类型、时长、比例和分辨率位于默认区。素材 URL、声音选项和视频数量位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
