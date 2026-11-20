# 生成与重跑

## 选择工作流、工作机与参数

1. 用 `workflows --scope public --search "关键词"` 搜索。范围包括 `public`、`mine`、`favorites`。可按 `--category image`、`--sort updated` 或 `--sort popular` 筛选和排序。有 `nextCursor` 时用 `--cursor` 翻页。记录工作流的 `id`、`versionId`。生成需要 API 格式工作流。
2. 用 `machines` 查看工作机名称、在线状态、节点数量和账户默认设置。按用户指定选择，未指定时可使用可用的默认工作机。用 `form <工作流ID> <工作机ID> --version <版本ID>` 读取实际参数，检查 `issues` 和必填字段。
3. 用字段 `id` 索引输入，按类型、范围及选项填写。浮点数可取范围内的值，步长用于控件增减。大整数按字段要求使用十进制字符串。参考素材用 `upload <本地文件> --asset-id <UUID>` 上传，输入值填写 `{"assetId": "上传返回的 ID"}`。账号里已有相同文件时，平台返回已有素材，返回的 ID 可能与传入的 UUID 不同。同一份上传重试沿用 UUID。

- 官方模板可用 `template-inputs <templates/index.json> <模板ID> <工作流ID> <工作机ID> [--version <版本ID>]` 准备默认素材。命令按对应 `sourceRevision` 下载、上传并绑定，返回输入值和上传后重新读取的表单哈希。发起生成时把结果合入提交 JSON，再填写执行次数和幂等键。

## 重跑以前的结果

- 用 `call execution.replay <执行ID>` 或 `call work.replay <作品ID>` 查到来源工作流、准确版本和来源记录 ID。
- 同一个 `form` 命令传入来源版本，再加 `--from-execution <执行ID>` 或 `--from-work <作品ID>`。逐项把需要保留的重跑值写入 `inputValues`。自己的执行可沿用有权限的参考素材。作品表单回填作者公开的值，`sharedAssets` 提供公开参考文件的预览地址。空的必填素材由当前用户提供。
- 提交时把相应来源写入 `sourceExecutionId` 或 `sourceWorkId`。一条任务使用一个来源。仅查看以前的参数时交付查询结果，用户要求生成时再提交。

## 提交与取回结果

- 把每套参数保存为一个 JSON 对象，保存单条对象或非空对象数组。字段为 `workflowId`、`versionId`、`machineId`、`executionCount`、`inputValues`、`inputSchemaHash` 和 `idempotencyKey`。表单返回的 `schemaHash` 用作 `inputSchemaHash`。切换版本或工作机后重新读取表单。每条任务生成一个独立幂等键，例如 UUID。
- `executionCount` 表示同一套参数的执行次数，平台为每次执行冻结种子。多套输入分别创建任务。用户只要求规划时交付参数方案。
- 用 `submit <任务文件>` 按顺序提交并保存任务 ID。失败时响应包含已受理任务、停止位置和剩余数量。响应不确定时，用原任务文件重试。明确拒绝且需修改的一项使用最新表单和新幂等键，其他条目的请求体与键照原样保留。提示「工作机输入配置已更新」时重新读取表单再改写这一项；提示「所选素材或来源已不可用」时重新上传素材或重新选择来源。
- `progress <任务ID>` 读取真实进度、排队原因和失败信息。任务由工作机领取执行。用户要求等待时持续查看，直至 `succeeded`、`failed` 或 `cancelled`。
- `results <任务ID>` 返回已完成的执行组及可访问的原文件链接，含任务部分失败前已经完成的结果。用 `download <成品ID> <目标文件>` 保存原件。
