# 平台操作

命令接在 Skill 客户端调用后。通用格式为 `call <操作> [位置参数 ...] [--query 字段=值] [--body 请求文件] [--out 目标文件]`。`operations` 返回操作、参数和请求文件类型。查询参数可重复传入不同的字段。分页结果通过 `nextCursor` 继续查询。下载和导出使用新文件名，保留原有文件。

## 个人资料

- `account` 查看当前账号的昵称和头像。`call account.nickname --body <JSON文件>` 保存 `nickname`，最长 32 个字符，使用 `null` 恢复显示账号名。
- `call account.avatar-upload --body <图片文件>` 上传或替换头像，支持 JPG、PNG 和 WebP，最大 5 MB。`call account.avatar-remove` 移除当前头像。
- `call author.get <账号名>` 读取有权限查看的作者资料。头像可通过返回的 `avatarUrl` 查看，或取其中的用户 ID 和版本，用 `call author.avatar <用户ID> <版本> --out <新文件.webp>` 下载。
- 维护账号使用 `call account.official-import-grants` 查看已获官方服务清单导入权限的账号。使用 `call account.set-official-import-grant <账号名> --body <JSON文件>` 管理授权。文件内容为 `{"granted":true}` 时授权，为 `{"granted":false}` 时撤销。获授权的账号可导入清单并更新自己名下的工作流。

## 工作流

API 默认使用部署的语言设置。可在子命令前传入 `--language zh`、`--language zh-tw`、`--language en`、`--language ja` 或 `--language ko`，用于官方条目、服务端错误等展示文案。工作流、任务、结果和作品使用相同的 ID 及访问权限。

| 网页操作                               | Skill 命令及参数                                                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 查公共库、个人和收藏工作流             | `workflows`，支持范围、分类、关键词、排序和分页                                                                                |
| 查看详情及指定版本                     | `call workflow.get <工作流ID>`，可加 `--query version_id=…`                                                                    |
| 查看可切换的版本                       | `call workflow.versions <工作流ID>`                                                                                            |
| 导入 ComfyUI JSON                      | `call workflow.import --body <文件>`，请求包含 `name`、`category`、`graph`                                                     |
| 改名、调整分类、更新工作流             | `call workflow.update <工作流ID> --body <文件>`，只写要改的 `name`、`category` 或 `graph`                                      |
| 收藏、取消收藏、查看收藏 ID            | `call workflow.favorite <工作流ID>`、`call workflow.unfavorite <工作流ID>`、`call workspace.favorites`                         |
| 分享链接和下载工作流 JSON              | `workflow-link <工作流ID>`、`call workflow.graph <工作流ID> --out <JSON文件>`，下载可指定版本                                  |
| 编辑参数名称、帮助、布局、控件和默认值 | `call workflow.set-layout <工作流ID> <版本ID> --body <文件>`                                                                   |
| 发布工作流                             | `call workflow.publish <工作流ID>`                                                                                             |
| 指定工作流封面                         | `call workflow.set-cover <工作流ID> --body <文件>`，请求含 `workId`（自己在该工作流下公开的作品，`null` 表示取最近公开的作品） |
| 删除工作流                             | `call workflow.delete <工作流ID>`                                                                                              |

导入时把源文件里的 JSON 对象写进 `graph`。媒体分类可用 `image`、`image_tool`、`video`、`video_tool`、`audio`、`3d`、`vector` 和 `llm`。官方专题分组使用 `node_basics`、`product_ads`、`character_fashion` 和 `brand_design`。官方模板使用 `import-template <templates/index.json> <模板ID> <API JSON文件>`，按索引分组带入分类。对已有工作流可用 `classify-template <templates/index.json> <模板ID> <工作流ID>` 核对及更新分类。

编辑 `graph` 会产生新版本。分享链接使用服务端现有的可见权限。发布会公开工作流的最新版本，发布前需要这个版本有成功执行。工作流封面取自作者公开的作品，可用 `call workflow.set-cover` 指定其中一件。删除工作流会归档记录，历史任务和结果仍可查看。

导入响应的 `format` 为 `api` 时可读取生成表单，为 `ui` 时保存编辑器图。Skill 对编辑器图在标准错误流提示导出 API JSON，标准输出仍可作为 JSON 读取。

修改参数布局时，先用 `form` 读取该版本和工作机的 `parameterLayout`、`parameterControls` 及 `originalDefaults`。写入 `{"machineId":"工作机 ID","parameterLayout":[…]}`。每项有 `fieldId`、`section` 和可选的 `displayName`、`help`、`control`、`defaultValue`。数组顺序就是区内顺序，区为 `default`、`advanced`、`hidden`。提交完整布局，保留未指定修改的项。撤销作者默认值可以将相应字段的 `defaultValue` 设为 `null`，并沿用 `originalDefaults`。操作后重新读取表单。

## 共享个人空间

- `call workspace.shares --query direction=sent` 列出有权查看当前账号空间的人。`call workspace.grant <账号名>` 授予整个「我的」的只读访问权限。`call workspace.revoke <受邀人ID>` 撤销。
- `call workspace.shares --query direction=received` 列出他人共享给当前账号的空间。`call workspace.shared <空间所有者ID>` 核对访问权限。读取共享空间时，在 `workflows`、`progress` 或 `results` 中传入 `--workspace-owner <空间所有者ID>`。也可在 `operations` 列出的相应读取操作中传入 `--query workspace_owner=<空间所有者ID>`。

## 团队空间

- `call team.list` 查当前账号可用的团队。`call team.create --body <JSON文件>` 创建团队，请求体含 `name`。`call team.members <团队ID>` 列出账号和角色。
- 管理员和所有者可用 `call team.rename <团队ID> --body <JSON文件>` 修改 `name`，用 `call team.avatar-upload <团队ID> --body <图片文件>` 上传头像，或用 `call team.avatar-remove <团队ID>` 移除头像。团队成员可从 `call team.get <团队ID>` 取得 `avatarUrl`，用 `call team.avatar <团队ID> <版本> --out <新文件.webp>` 下载。
- 管理员和所有者可用 `call team.set-profile-visibility <团队ID> --body <JSON文件>` 设置布尔字段 `public`。团队开启且有公开内容时，`call team.public-profile <团队ID>` 可读取公开主页资料。用 `call work.list --query public_team_id=<团队ID>` 查看团队主页中的作品。工作流列表接口 `GET /api/v1/workflows` 也接收 `public_team_id`。
- `call team.set-member <团队ID> <账号名> --body <JSON文件>` 添加成员或更改角色，请求体的 `role` 可为 `reader`、`editor` 或 `manager`，具体取决于当前账号权限。`call team.remove-member <团队ID> <成员ID>` 移除成员或退出团队。所有者可用 `call team.transfer <团队ID> <成员ID>` 转让所有权，或用 `call team.archive <团队ID>` 归档。
- 归档前需先处理排队或执行中的任务。所有者可用 `call team.archived` 查看自己拥有的归档团队与排队状态，用 `call team.restore <团队ID>` 恢复原团队。此前已发布的工作流和作品会重新公开，旧归档中的排队任务可以继续由工作机领取。
- 用 `workflows --workspace-team <团队ID>` 查团队工作流。相应的详情、版本、图文件和资产库读取操作使用 `--query workspace_team=<团队ID>`。用 `call team.import-workflow <团队ID> --body <JSON文件>` 导入 ComfyUI JSON，其中 `graph` 保存工作流图。用 `call team.copy-workflow <团队ID> <个人工作流ID>` 复制本人工作流，可用 `--query version_id=…` 选择版本。
- 用 `call team.upload-asset <团队ID> <新素材UUID> --query filename=<文件名> --body <素材文件>` 上传到团队，或用 `call team.copy-asset <团队ID> <个人素材ID>` 复制本人素材。团队素材列表用 `call asset.list --query workspace_team=<团队ID>` 查询。上传封面时加 `--query save_to_library=false`，再用返回的素材 ID 设置工作流封面。

## 项目

- `call project.list` 和 `call project.get <项目ID>` 读取当前空间的项目。列表默认读取进行中的项目，使用 `--query archived=true` 查看归档项目。读取团队或个人共享项目时分别传 `--query workspace_team=<团队ID>` 或 `--query workspace_owner=<空间所有者ID>`。
- `call project.create --body <JSON文件>` 创建项目，请求带 `name` 和可选的 `description`。`call project.link-material <项目ID> <workflows或assets> <记录ID>` 关联现有资料，`call project.unlink-material` 用相同的位置参数移出。操作团队项目时带 `--query workspace_team=<团队ID>`。
- `call project.update <项目ID> --body <JSON文件>` 保存进行中项目的 `name` 和 `description`。`call project.archive <项目ID> --body <JSON文件>` 使用 `{"archived": true}` 归档，使用 `{"archived": false}` 恢复。用 `call project.delete <项目ID>` 删除，用 `call project.restore <项目ID>` 撤销删除。归档和删除保留原空间中的工作流、素材、任务、结果和作品。团队的归档、删除及恢复由管理员和所有者操作。
- `call task.change-project <任务ID> --body <JSON文件>` 的 `projectId` 接收同空间的项目 ID 或 `null`，整批结果和关联的作品随任务移动。用对应列表的 `--query project_id=<项目ID>` 查看归集内容。工作流和作品使用 `scope=mine`。
- 个人生成时在提交计划中填写可选的 `projectId`。同一空间的重跑接口会返回仍在进行中的来源项目，按用户指定的归属填写。

## 任务、执行和素材

用 `call task.change-machine <任务ID> --body <文件>` 为排队中、尚未领取的 ComfyUI 任务指定另一台自有在线 ComfyUI 工作机，请求体为 `{"machineId":"目标工作机 ID"}`。目标校验通过后，任务进入目标队尾。任务进度中的 `queueAhead` 是前方还未领取的平台任务数。

用 `progress <任务ID>` 查看各次执行的恢复状态。补跑可重试的执行时，调用 `call task.retry-executions <任务ID> --body <文件>`，传入从 0 开始的 `executionIndices` 和新的 `idempotencyKey`。ComfyUI 任务另传 `machineId`。官方和 RunningHub 任务另传 `"service": true`，RunningHub 沿用原连接及其凭据版本。平台复用所选执行的参数与种子。同一次补跑如果响应不确定，原样重试。

| 网页操作                         | Skill 命令及参数                                                                                                                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 查看任务历史、活动任务和详情     | `call task.list`、`call task.activity`、`call task.get <任务ID>`                                                                                                                  |
| 查看进度和来源参数               | `progress <任务ID>`、`call task.inputs <任务ID>`                                                                                                                                  |
| 下载任务版本的工作流             | `call task.graph <任务ID> --out <JSON文件>`                                                                                                                                       |
| 取消排队任务、删除已结束记录     | `call task.cancel <任务ID>`、`call task.delete <任务ID>`                                                                                                                          |
| 查看结果和单次执行实际参数       | `results <任务ID>`、`call execution.list`、`call execution.get <执行ID>`                                                                                                          |
| 查看成品、下载预览或原件         | `call artifact.list`、`call artifact.thumbnail <成品ID> --out <文件>`、`call artifact.video-preview <成品ID> --out <文件>`、`download <成品ID> <文件>`                            |
| 指定结果分组封面                 | `call execution.set-cover <执行ID> --body <文件>`，用 `artifactId` 选择本次的成品图或视频，用 `assetId` 选择已上传的图片，传 `{}` 恢复默认。视频可用 `frameMs` 选画面，单位毫秒。 |
| 删除单个成品或整组结果           | `call artifact.delete <成品ID>`、`call execution.delete-artifacts <执行ID>`                                                                                                       |
| 查看、下载、清理未使用的私有素材 | `call asset.get <素材ID>`、`call asset.download <素材ID> --out <文件>`、`call asset.delete <素材ID>`                                                                              |

可用 `--query workflow_id=…`、`--query task_id=…` 或 `--query execution_id=…` 缩小相应列表。`call execution.list`、`call task.list` 和 `call task.activity` 支持用 `--query version_id=…` 按版本筛选。任务列表还可用 `--query state=active`（排队或执行中）、`succeeded`、`failed`、`cancelled` 按状态筛选。媒体响应中的文件和预览地址用于打开对应内容，私有内容沿用账号权限。已被任务引用的素材和已被作品引用的成品由服务端保护。取消任务、删除任务记录、删除成品是独立操作。误删后可用 `call workflow.restore`、`call task.restore`、`call work.restore`、`call artifact.restore` 加对应 ID 撤销删除，`call execution.restore-artifacts <执行ID>` 撤销最近一次整组删除，`call task.resume <任务ID>` 让未开始执行就取消的任务回到队列。

`call execution.list` 可用 `--query workflow_name=…` 按提交时的工作流名称搜索。用 `--query created_from=…` 和 `--query created_before=…` 按执行创建时间筛选，单位为 Unix 毫秒。起点包含在范围内，终点为排他边界。

## 个人资产库

- 使用 `upload <素材文件> --save-to-library` 上传并存入资产库。已有私有素材使用 `call asset.save-to-library <素材ID>`。可作为输入的生成成品使用 `call artifact.save-to-library <成品ID>`。
- 使用 `call asset.list` 查看本账号保存的素材。可用 `--query search=…` 搜索文件名，或用 `--query kind=image`、`video`、`audio` 或 `3d` 筛选类型。按工作流允许的 MIME 筛选时，可重复传入 `--query content_types=…`。使用返回的素材 ID 填写生成输入的 `assetId`。
- 使用 `call asset.remove-from-library <素材ID>` 移出资产库。已有任务引用的素材按任务的保留规则管理。没有任务引用的素材记录会被删除。

## 个人云端工作机

`machines` 返回账号的工作机和可添加的连接类型。`call machine.add-connection --body <文件>` 接收 `kind`、`scope`、`name` 和 `apiKey`。用 `call machine.update-connection <工作机ID> --body <文件>` 提交相同字段以更换 API Key，沿用原来的 `kind` 和 `scope`。新任务使用新 Key，已有任务要使用新 Key 需重新提交。将含 Key 的请求文件保存在用户的私有目录。用 `call workflow.import-reference --body <文件>` 提交 `machineId` 和 `reference`，其中 `reference` 为云端工作流链接或 ID。返回版本的 `worker.kind` 和 `worker.scope` 决定可用连接。生成时沿用 `form` 和 `submit`，两次请求使用同一台个人工作机。

## 作品

- 用 `call work.list --query scope=public` 或 `--query scope=mine` 查作品，可加 `--query workflow_id=…` 和 `--query version_id=…`。加 `--query current_version_only=true` 可只查来源工作流当前发布版本的作品。用 `call work.get <作品ID>` 查详情，用 `call work.artifacts <作品ID>` 获取所选成品，用 `call work.inputs <作品ID>` 读取公开的输入字段和参考素材地址。
- 用 `call work.asset-download <作品ID> <素材ID> --out <文件>` 保存作品公开的参考素材，或用 `call work.asset-thumbnail <作品ID> <素材ID> --out <文件>` 保存图像或视频的缩略图。
- 发布使用 `call work.publish --body <文件>`。写入稳定的 UUID `id`、`executionId`、`title` 和 `artifactIds`。用 `coverArtifactId` 选择同次执行的图片，或用已选中公开的视频作为封面。视频可通过 `coverFrameMs` 指定画面，单位毫秒。按确认的范围传 `shareParameters: true` 公开标量参数，或传 `shareAssets: true` 公开这次的参数与参考文件。省略两者时按 API 默认范围公开成品及已选的封面。响应不确定时复用同一个 UUID 和请求体。
- 服务端要求作品关联的工作流已经发布，且这次执行所用的版本也已发布。来自旧草稿版本的结果不能发布为作品；来自最新版本时，发布工作流会同时发布这个版本。用户只授权发布作品时，以此条件提示用户。用户也明确授权发布工作流时，按工作流发布规则先处理。
- 全部成品都是文本，或所选成品含有音频或 3D 模型时，可以省略封面。独立封面可通过 `coverAssetId` 指定已上传的图片，或通过 `executionCoverSha256` 继承发布预览时的独立结果封面。后者取自结果的 `coverImage.sha256`，结果封面变更时需重新确认。
- 有 `coverImage` 时用它预览独立封面。播放、查看和下载原件时，使用 `work.artifacts` 返回的实际成品。仅用于封面的成品图通过作品的缩略图地址展示。
- `call work.set-cover <作品ID> --body <文件>` 更换已发布作品的封面，支持 `artifactId`、`assetId` 和恢复默认的 `{}`。独立封面的缩略图可用 `call execution.cover-thumbnail <执行ID> <摘要> --out <文件>` 或 `call work.cover-thumbnail <作品ID> <摘要> --out <文件>` 保存。
- 取消公开用 `call work.unpublish <作品ID>`，删除作品记录用 `call work.delete <作品ID>`。重跑见[生成与重跑](generation.md)。

## 工作机

- `machines` 的 `runtime.version` 是工作机上报的运行版本。用户要求更新某台工作机时，确认该机的 `updateAvailable`，运行 `call machine.update <工作机ID>`。工作机在本次任务交付后获取当时的最新签名包。用 `machines` 查看等待、更新和失败状态。
- `machines` 显示默认工作机、连接状态和密钥前缀。添加时使用 `machine-create <名称> --out <新的 worker.json 路径>`。重置密钥使用 `machine-rotate <工作机ID> --out <新的 worker.json 路径>`。`worker-bundle <目标ZIP>` 可下载工作机启动包，包内已写入平台地址，解压后运行即可申请接入。
- 新配置写入仓库外的用户私有目录。配置默认使用当前平台地址以及 `http://127.0.0.1:8188` 的 ComfyUI 地址。工作机需要其他地址时使用 `--platform-url` 与 `--comfy-url`。把配置与启动包交给用户在工作机上运行。通过 `machines` 查看实际连接结果。
- 账号管理：`call account.password`、`call account.email`、`call account.delete` 都要在 JSON 里带当前密码，由用户本人提供，不要代填或保存。`account.password` 修改密码后，其他登录会话失效，所有个人工作机被撤销。ComfyUI 工作机需要重置密钥后重新连接，RunningHub 需要重新添加连接。`account.delete` 注销账号且不可恢复，执行前必须得到用户明确确认。`account.password-reset` 和 `account.password-reset-confirm` 用于邮件找回。`account.email` 填写的新邮箱先显示为 `pendingEmail`，用户点击确认邮件里的链接（或用 `call account.email-confirm` 提交邮件里的 `token`）后才生效。
- 没有密钥的工作机启动后会显示接入代码。用 `call machine.link <代码>` 查看申请，结果里有申请时间、来源地址和 `sameNetwork`（IPv4 比较地址，IPv6 比较 /64 网段，无从比较时为 `null`）。申请状态为 `pending` 时，向用户说明这些信息并核对是用户自己启动的工作机。新增工作机用 `{"name":"名称"}`，重装后重新连接用 `{"machineId":"工作机ID"}`。重新连接前用 `machines` 核对目标属于当前账号，且未撤销、离线、空闲。把请求体写入 JSON 文件，再用 `call machine.link-approve <代码> --body <文件>` 确认接入。`approved` 表示等待工作机领取密钥，`linked` 表示密钥已发放。重新连接会换发密钥，原工作机的排队任务会继续等待。
- 用 `call machine.set-default <工作机ID>` 更改默认设置。用 `call machine.revoke <工作机ID>` 撤销。重置或撤销会使原密钥失效并终止该机执行中的任务；重置后排队任务继续等待这台工作机，撤销会同时结束排队任务。操作前核对目标。若连接中断造成结果不确定，先查看工作机状态与配置文件，避免重复签发。
- 用 `call machine.delete <工作机ID>` 从列表移除已撤销的工作机。历史任务保留工作机名称。
- 用 `call machine.get <工作机ID>` 查看运行版本、最近联络时间、更新状态、当前任务和排队数。用 `call machine.rename <工作机ID> --body <文件>` 保存包含 `name` 的 JSON，更新平台显示名。
- 用 `call machine.pause <工作机ID> --body <文件>` 设置 ComfyUI 工作机的接单状态。JSON 中的 `{"paused":true}` 暂停接单，`{"paused":false}` 恢复接单。已经领取的任务继续执行并回传，排队任务等恢复后领取。
