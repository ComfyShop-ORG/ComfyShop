# 平台操作

命令接在 Skill 客户端调用后。通用格式为 `call <操作> [记录ID ...] [--query 字段=值] [--body JSON文件] [--out 目标文件]`。`operations` 返回实际支持的操作和参数。查询参数可重复传入不同的字段。分页结果通过 `nextCursor` 继续查询。下载和导出使用新文件名，保留原有文件。

## 工作流

| 网页操作                               | Skill 命令及参数                                                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 查公共库、个人和收藏工作流             | `workflows`，支持范围、分类、关键词、排序和分页                                                                                |
| 查看详情及指定版本                     | `call workflow.get <工作流ID>`，可加 `--query version_id=…`                                                                    |
| 导入 ComfyUI JSON                      | `call workflow.import --body <文件>`，请求包含 `name`、`category`、`graph`                                                     |
| 改名、调整分类、更新工作流             | `call workflow.update <工作流ID> --body <文件>`，只写要改的 `name`、`category` 或 `graph`                                      |
| 收藏、取消收藏、查看收藏 ID            | `call workflow.favorite <工作流ID>`、`call workflow.unfavorite <工作流ID>`、`call workspace.favorites`                         |
| 分享链接和下载工作流 JSON              | `workflow-link <工作流ID>`、`call workflow.graph <工作流ID> --out <JSON文件>`，下载可指定版本                                  |
| 编辑参数名称、帮助、布局、控件和默认值 | `call workflow.set-layout <工作流ID> <版本ID> --body <文件>`                                                                   |
| 发布工作流                             | `call workflow.publish <工作流ID>`                                                                                             |
| 指定工作流封面                         | `call workflow.set-cover <工作流ID> --body <文件>`，请求含 `workId`（自己在该工作流下公开的作品，`null` 表示取最近公开的作品） |
| 删除工作流                             | `call workflow.delete <工作流ID>`                                                                                              |

导入时把源文件里的 JSON 对象写进 `graph`，分类使用 `image`、`video` 或 `tool`。编辑 `graph` 会产生新版本。分享链接使用服务端现有的可见权限。发布会公开工作流的最新版本，发布前需要这个版本有成功执行。工作流封面取自作者公开的作品，可用 `call workflow.set-cover` 指定其中一件。删除工作流会归档记录，历史任务和结果仍可查看。

修改参数布局时，先用 `form` 读取该版本和工作机的 `parameterLayout`、`parameterControls` 及 `originalDefaults`。写入 `{"machineId":"工作机 ID","parameterLayout":[…]}`。每项有 `fieldId`、`section` 和可选的 `displayName`、`help`、`control`、`defaultValue`。数组顺序就是区内顺序，区为 `default`、`advanced`、`hidden`。提交完整布局，保留未指定修改的项。撤销作者默认值可以将相应字段的 `defaultValue` 设为 `null`，并沿用 `originalDefaults`。操作后重新读取表单。

## 任务、执行和素材

| 网页操作                         | Skill 命令及参数                                                                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 查看任务历史、活动任务和详情     | `call task.list`、`call task.activity`、`call task.get <任务ID>`                                                                                       |
| 查看进度和来源参数               | `progress <任务ID>`、`call task.inputs <任务ID>`                                                                                                       |
| 下载任务版本的工作流             | `call task.graph <任务ID> --out <JSON文件>`                                                                                                            |
| 取消排队任务、删除已结束记录     | `call task.cancel <任务ID>`、`call task.delete <任务ID>`                                                                                               |
| 查看结果和单次执行实际参数       | `results <任务ID>`、`call execution.list`、`call execution.get <执行ID>`                                                                               |
| 查看成品、下载预览或原件         | `call artifact.list`、`call artifact.thumbnail <成品ID> --out <文件>`、`call artifact.video-preview <成品ID> --out <文件>`、`download <成品ID> <文件>` |
| 指定结果分组封面                 | `call execution.set-cover <执行ID> --body <文件>`，请求含 `artifactId`；封面是视频时可加 `frameMs`（取哪一刻的画面，毫秒，须在视频长度内）             |
| 删除单个成品或整组结果           | `call artifact.delete <成品ID>`、`call execution.delete-artifacts <执行ID>`                                                                            |
| 查看、下载、清理未使用的私有素材 | `call asset.get <素材ID>`、`call asset.download <素材ID> --out <文件>`、`call asset.delete <素材ID>`                                                   |

可用 `--query workflow_id=…`、`--query task_id=…` 或 `--query execution_id=…` 缩小相应列表。任务列表还可用 `--query state=active`（排队或执行中）、`succeeded`、`failed`、`cancelled` 按状态筛选。媒体响应中的文件和预览地址用于打开对应内容，私有内容沿用账号权限。已被任务引用的素材和已被作品引用的成品由服务端保护。取消任务、删除任务记录、删除成品是独立操作。误删后可用 `call workflow.restore`、`call task.restore`、`call work.restore`、`call artifact.restore` 加对应 ID 撤销删除，`call execution.restore-artifacts <执行ID>` 撤销最近一次整组删除，`call task.resume <任务ID>` 让未开始执行就取消的任务回到队列。

## 作品

- 用 `call work.list --query scope=public` 或 `--query scope=mine` 查作品，可加 `--query workflow_id=…`。用 `call work.get <作品ID>` 查详情，用 `call work.artifacts <作品ID>` 获取所选成品，用 `call work.inputs <作品ID>` 读取作者公开的参数及字段名称。
- 发布使用 `call work.publish --body <文件>`。写入稳定的 UUID `id`、`executionId`、`title`、`artifactIds`、`coverArtifactId` 和 `shareParameters`。封面是视频时可加 `coverFrameMs` 指定取哪一刻的画面（毫秒）；封面的 `media.thumbnail.src` 已包含所选画面，直接在后面加 `?size=` 读取，或用 `call artifact.cover-frame <成品ID> <毫秒> --out <文件>` 保存，只能读取已被选作封面的时间点。成品和封面来自同一次成功执行，封面是所选成品之一。只有用户明确要求公开参数时才把 `shareParameters` 设为 `true`。响应不确定时复用同一个 UUID 和请求体。
- 服务端要求作品关联的工作流已经发布，且这次执行所用的版本也已发布。来自旧草稿版本的结果不能发布为作品；来自最新版本时，发布工作流会同时发布这个版本。用户只授权发布作品时，以此条件提示用户。用户也明确授权发布工作流时，按工作流发布规则先处理。
- 取消公开用 `call work.unpublish <作品ID>`，删除作品记录用 `call work.delete <作品ID>`。重跑见[生成与重跑](generation.md)。

## 工作机

- `machines` 显示默认工作机、连接状态和密钥前缀。添加时使用 `machine-create <名称> --out <新的 worker.json 路径>`。重置密钥使用 `machine-rotate <工作机ID> --out <新的 worker.json 路径>`。`worker-bundle <目标ZIP>` 可下载工作机启动包，包内已写入平台地址，解压后运行即可申请接入。
- 新配置写入仓库外的用户私有目录。配置默认使用当前平台地址以及 `http://127.0.0.1:8188` 的 ComfyUI 地址。工作机需要其他地址时使用 `--platform-url` 与 `--comfy-url`。把配置与启动包交给用户在工作机上运行。通过 `machines` 查看实际连接结果。
- 账号管理：`call account.password`、`call account.email`、`call account.delete` 都要在 JSON 里带当前密码，由用户本人提供，不要代填或保存。`account.password` 修改密码后，其他登录和全部工作机密钥失效，工作机需重置密钥后重新连接。`account.delete` 注销账号且不可恢复，执行前必须得到用户明确确认。`account.password-reset` 和 `account.password-reset-confirm` 用于邮件找回。`account.email` 填写的新邮箱先显示为 `pendingEmail`，用户点击确认邮件里的链接（或用 `call account.email-confirm` 提交邮件里的 `token`）后才生效。
- 首次启动的工作机会显示接入代码。用 `call machine.link <代码>` 查看申请，结果里有申请时间、来源地址和 `sameNetwork`（来源是否与当前客户端在同一网络，无从比较时为 `null`）。向用户说明这些信息，核对是用户自己启动的机器后，把 `{"name":"名称"}` 写入 JSON 文件，再用 `call machine.link-approve <代码> --body <文件>` 确认接入。
- 用 `call machine.set-default <工作机ID>` 更改默认设置。用 `call machine.revoke <工作机ID>` 撤销。重置或撤销会使原密钥失效并终止该机执行中的任务；重置后排队任务继续等待这台工作机，撤销会同时结束排队任务。操作前核对目标。若连接中断造成结果不确定，先查看工作机状态与配置文件，避免重复签发。
