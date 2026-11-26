# 生成与重跑

## 选择工作流、工作机与参数

1. 用 `workflows --scope public --search "关键词"` 搜索。范围包括 `public`、`mine`、`favorites`。可按 `--category image`、`--sort updated` 或 `--sort popular` 筛选和排序。有 `nextCursor` 时用 `--cursor` 翻页。记录工作流的 `id`、`versionId` 和 `format`。需要指定 API 的展示语言时，在子命令前使用 `--language`。
2. 根据 `format` 读取实际表单，检查 `issues` 和必填字段。
   - `service` 使用 `form <工作流ID> --service --version <版本ID>`。提交后由 `worker.kind` 指定的平台工作机领取。
   - `api` 使用 `machines` 查看自己的工作机，选择 `online` 为 `true` 的机器。用户未指定时可使用在线的默认工作机。`paused` 为 `true` 的工作机在恢复接单后领取排队任务。用 `form <工作流ID> <工作机ID> --version <版本ID>` 读取表单。
   - `remote` 使用自己的 RunningHub 连接。用 `machines` 查找与该版本的 `worker.kind` 和 `worker.scope` 匹配的连接，再用 `form <工作流ID> <工作机ID> --version <版本ID>` 读取表单。提交时填写同一个 `machineId`，费用计入该连接对应的 RunningHub 账号。
   - `ui` 需要先从 ComfyUI 导出 API 格式并导入平台，再选择该版本生成。
3. 用 `fields` 里的字段 `id` 索引输入，按类型、范围及选项填写。提交 `choices` 中的原始值，`parameterPresentation` 里该字段的 `choiceLabels` 用于展示选项。普通整数须符合范围和步长，种子可取范围内的整数，字段要求大整数时用十进制字符串。浮点数可取范围内的值。参考素材用 `upload <本地文件> --asset-id <UUID>` 上传，输入值填写 `{"assetId": "上传返回的 ID"}`。账号里已有相同文件时，平台返回已有素材，返回的 ID 可能与传入的 UUID 不同。同一份上传重试沿用 UUID。

- 只调整本次生成时，把变更写入任务的 `inputValues`，包含用户明确要调整的隐藏字段。新生成可让平台用当前工作流默认值补齐其余字段。用户要修改该版本的布局或默认值时，使用 `call workflow.set-layout`。
- 调整画幅或参考帧时，从 `outputSizes`、`referenceTimelines` 确认关联字段，按表单给出的帧率和帧数约束核对参考帧时间。若画幅绑定了 `promptFieldId`，修改画幅或提示词后，用所选比例更新该字段的首行（例如 `Aspect ratio: 16:9`），下一行开始写提示词正文。原样重跑时使用历史输入。
- 从官方模板索引导入、由个人工作机执行的 ComfyUI 工作流可用 `template-inputs <templates/index.json> <模板ID> <工作流ID> <工作机ID> [--version <版本ID>] [--source-revision <完整提交SHA>]` 准备默认素材。素材记录有 `sourceRevision` 时使用该值，省略时传入索引来源的 40 位小写 Git 提交 SHA。命令按固定版本下载、上传并绑定素材，返回输入值和上传后重新读取的表单哈希。发起生成时把结果合入提交 JSON，再填写执行次数和幂等键。

## 重跑以前的结果

- 用 `call execution.replay <执行ID>` 或 `call work.replay <作品ID>` 查到来源工作流、准确版本和来源记录 ID。
- 在对应的 `form` 命令中传入来源版本，再加 `--from-execution <执行ID>` 或 `--from-work <作品ID>`。例如 `form <工作流ID> --service --version <来源版本ID> --from-work <作品ID>` 可读取官方模型的作品参数。把表单中需要保留的历史 `default` 值复制到 `inputValues`，再覆盖用户这次要调整的字段。自己的执行可沿用有权限的参考素材。
- 复用作品的公开参考素材时，把对应字段 `default` 中的 `{"assetId": "素材 ID"}` 原样写入 `inputValues`。`sharedAssets` 提供预览地址，平台在提交时按当前账号的配额登记所选素材。仍为空的必填素材由当前用户提供。
- 提交时把相应来源写入 `sourceExecutionId` 或 `sourceWorkId`。一条任务使用一个来源。仅查看以前的参数时交付查询结果，用户要求生成时再提交。

## 从成品继续局部重绘

- 用 `call artifact.inpaint-targets <成品ID>` 查可用的工作流版本、工作机和参考图字段。按名称选工作流时，使用 `workflows --inpaint-artifact <成品ID> --scope mine --search "关键词"` 搜索当前空间，`--scope public` 搜索公开工作流。团队成品查询分别带 `--query workspace_team=<团队ID>` 和 `--workspace-team <团队ID>`。
- 选定目标后，用 `call artifact.use-as-input <成品ID>` 取得原图的素材 ID，团队操作带 `--query workspace_team=<团队ID>`。在目标版本的表单里，将这份素材填入 `fieldId`。新画的遮罩使用与原图同尺寸的 PNG，红通道 255 表示重绘、0 表示保留。上传遮罩后将素材 ID 填入 `mask.fieldId`，有 `mask.channelFieldId` 时将该字段设为 `red`。单个 `LoadImage` 兼用图片和遮罩时，省略遮罩字段会沿用原图自带的透明通道。确认参数后用 `submit` 提交。
- 在团队空间使用 `form` 和 `submit` 时均带 `--workspace-team <团队ID>`。上传本次的遮罩用 `call team.upload-asset <团队ID> <新素材UUID> --query filename=mask.png --query save_to_library=false --body <遮罩文件>`。

## 查询预计费用

官方工作流的表单返回 `costEstimate: true` 时，用 `call task.cost-estimate --body <JSON文件>` 查询一次执行的费用。请求包含 `workflowId`、`versionId`、`inputSchemaHash` 和 `inputValues`，重跑时可加相应的来源 ID。团队报价加 `--query workspace_team=<团队ID>`。

向用户报告 `unitPrice` 和 `currency`，按执行次数计算本批金额。`estimated: true` 时说明费用按实际生成用量结算。调用报价前说明供应商会收到本次报价使用的私有参考素材。报价只查询费用，生成使用 `submit`。

## 提交与取回结果

下面是带 `prompt` 字段的官方模型任务文件示例。用实际工作流 ID、版本 ID、表单哈希和本次提交新建的 UUID 替换占位值。

```json
{
  "workflowId": "<工作流ID>",
  "versionId": "<版本ID>",
  "executionCount": 1,
  "inputValues": { "prompt": "海上日出" },
  "inputSchemaHash": "<表单返回的 schemaHash>",
  "idempotencyKey": "<本次提交的 UUID>"
}
```

- 把每套参数保存为一个 JSON 对象，保存单条对象或非空对象数组。官方任务省略 `machineId`，个人工作机任务填写读取表单时选用的 `machineId`。切换版本或工作机后重新读取表单。每条任务生成一个独立幂等键，例如 UUID。
- `executionCount` 表示同一套参数的执行次数，平台为每次执行冻结种子。多套输入分别创建任务。用户只要求规划时交付参数方案。
- 用 `submit <任务文件>` 按顺序提交，从响应的 `tasks` 中记录已受理任务的 ID。失败时响应包含已受理任务、停止位置和剩余数量。响应不确定时，用原任务文件重试。明确拒绝且需修改的一项使用最新表单和新幂等键，其他条目的请求体与键照原样保留。提示「工作机输入配置已更新」时重新读取表单再改写这一项；提示「所选素材或来源已不可用」时重新上传素材或重新选择来源。
- `progress <任务ID>` 读取真实进度、排队原因和失败信息。任务由工作机领取执行。用户要求等待时持续查看，直至 `succeeded`、`failed` 或 `cancelled`。
- `results <任务ID>` 返回已完成的执行组及可访问的原文件链接，含任务部分失败前已经完成的结果。用 `download <成品ID> <目标文件>` 保存原件。
