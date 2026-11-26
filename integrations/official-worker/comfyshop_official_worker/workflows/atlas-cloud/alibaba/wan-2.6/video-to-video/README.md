# Wan 2.6 视频生视频

参考一至三段视频的人物、主体与声音生成新视频。 Atlas Cloud 模型 ID 为 `alibaba/wan-2.6/video-to-video`。[官方模型 API](https://www.atlascloud.ai/models/alibaba/wan-2.6/video-to-video)

## Atlas 接口参数

| Atlas 参数                | ComfyShop 字段                                                        | 必填     | 默认值                           | 输入约定                                                                                                                   |
| ------------------------- | --------------------------------------------------------------------- | -------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `model`                   | `execution.config.model`                                              | 是       | `alibaba/wan-2.6/video-to-video` | 工作机从执行配置读取                                                                                                       |
| `prompt`                  | `prompt`                                                              | 是       | 无                               | 用 `character1` 等按参考视频顺序指代主体，最多 1,500 字符                                                                  |
| `negative_prompt`         | `negative_prompt`                                                     | 否       | 无                               | 最多 500 字符，留空时省略                                                                                                  |
| `videos`                  | `reference_video_1` 至 `reference_video_3`、`reference_video_sources` | 是       | 无                               | 一至三段 MP4 或 MOV，每段 2 至 30 秒，小于 100 MB                                                                          |
| `size`                    | `size`                                                                | 是       | `1280*720`                       | `1280*720`、`720*1280`、`960*960`、`1088*832`、`832*1088`、`1920*1080`、`1080*1920`、`1440*1440`、`1632*1248`、`1248*1632` |
| `duration`                | `duration`                                                            | 否       | 5                                | `5` 或 `10` 秒                                                                                                             |
| `enable_prompt_expansion` | `enable_prompt_expansion`                                             | 条件必填 | true                             | 控制提示词优化，`shot_type=multi` 时须为 `true`                                                                            |
| `shot_type`               | `shot_type`                                                           | 否       | `multi`                          | `multi` 多镜头或 `single` 单镜头                                                                                           |
| `seed`                    | `seed`                                                                | 否       | -1                               | 整数范围 -1 至 2147483647。-1 使用随机种子                                                                                 |

工作机先提交上传视频，再按行追加公开 URL。样例数据包含 `aspect_ratio`，请求 Schema 通过 `size` 指定宽高。提示词限制参照厂商的参考生视频约定。[阿里云参考生视频参数](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/legacy-wan-reference-to-video-api-reference) · [官方 Schema](https://static.atlascloud.ai/model/schema/alibaba-wan-2.6-video-to-video.json) · [官方示例数据](https://static.atlascloud.ai/model/example/alibaba-wan-2.6-video-to-video.json) · [模型说明](https://static.atlascloud.ai/model/readme/alibaba-wan-2.6-video-to-video.md)

## API 调用

使用 `Authorization: Bearer <API_KEY>`，将以下 JSON 发送到 `POST https://api.atlascloud.ai/api/v1/model/generateVideo`。[官方端点文档](https://www.atlascloud.ai/docs/more-models/alibaba/wan-2.6-video-to-video/generateVideo) · [官方调用示例](https://www.atlascloud.ai/models/alibaba/wan-2.6/video-to-video#usage-examples)

```json
{
  "model": "alibaba/wan-2.6/video-to-video",
  "prompt": "character1 走进画室，镜头从门口移动到侧面，最后停在工作台。",
  "videos": ["https://example.com/character.mp4"],
  "size": "1920*1080",
  "duration": 10,
  "enable_prompt_expansion": true,
  "shot_type": "multi",
  "seed": -1
}
```

从响应取 `data.id`，轮询 `GET https://api.atlascloud.ai/api/v1/model/prediction/{id}`。工作机按 `data.outputs` 的顺序保存视频。[预测文档](https://www.atlascloud.ai/docs/predictions)

## ComfyShop 同步

提示词、首段参考视频、尺寸、时长与镜头模式位于默认区。其余素材、公开地址、负面提示词、扩写和种子位于高级区。[工作流清单与五种译文](workflow.json)

从仓库根目录运行 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync`。[官方工作机配置](../../../../../../../../docs/deployment.md#官方工作机)
