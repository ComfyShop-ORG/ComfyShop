# 架构

## 代码阅读顺序

从你在网页或工作机上遇到的操作出发，按每行的顺序读。文件开头说明它负责哪一段，关键函数旁可以查到输入、返回结果和失败条件。

从仓库根目录运行 `uv run --all-packages pytest`，后接测试文件路径和表内的 `-k` 筛选。浏览器用例使用表内的 pnpm 命令。

| 想弄清的行为             | 顺序                                                                                                                                                                                                                                                                                                        | 先跑哪个测试                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 平台启动时读取什么       | [环境变量示例](../.env.example) → [配置加载](../apps/api/src/comfyshop_api/core/config.py) → [API 入口](../apps/api/src/comfyshop_api/main.py)                                                                                                                                                              | [配置注入](../apps/api/tests/test_health.py) `-k health_uses_dependency`                             |
| 点击生成后如何保存任务   | [运行表单](../apps/web/src/features/workflows/run-form.tsx) → [接口客户端](../packages/api-client/src/index.ts) → [任务接口](../apps/api/src/comfyshop_api/api/tasks.py) → [任务提交](../apps/api/src/comfyshop_api/services/tasks.py) → [输入校验与冻结](../apps/api/src/comfyshop_api/services/inputs.py) | [掉线后的提交与重试](../apps/api/tests/test_task_activity.py) `-k offline_machine_rejects_new_tasks` |
| 工作机如何领取和断线恢复 | [工作机主循环](../integrations/comfyui/comfyshop_worker/runner.py) → [领取与回传接口](../apps/api/src/comfyshop_api/api/worker.py) → [领取与租约](../apps/api/src/comfyshop_api/services/machines.py) → [ComfyUI 执行与恢复](../integrations/comfyui/comfyshop_worker/comfy.py)                             | [并发领取与租约过期](../apps/api/tests/test_worker.py) `-k concurrent_claims_are_exclusive`          |
| 成品如何回传和保存       | [成品接口](../apps/api/src/comfyshop_api/api/artifacts.py) → [回传校验与记录](../apps/api/src/comfyshop_api/services/artifacts.py) → [媒体接收](../apps/api/src/comfyshop_api/services/media_uploads.py)                                                                                                    | [逐次成品清单](../apps/api/tests/test_outputs.py) `-k batch_and_multi_output`                        |
| 谁可以打开成品           | [成品读取接口](../apps/api/src/comfyshop_api/api/artifacts.py) → [作品的公开授权](../apps/api/src/comfyshop_api/services/works.py)                                                                                                                                                                          | [作品授权的成品范围](../apps/api/tests/test_outputs.py) `-k work_subset_cover_grants`                |
| 结果如何翻页和返回原处   | [结果列表](../apps/web/src/components/execution-collection.tsx) → [执行详情](../apps/web/src/components/execution-dialog.tsx) → [列表分页与选择](../apps/web/src/components/use-collection-navigation.ts) → [可见卡片渲染](../packages/media/src/index.tsx)                                                 | [桌面与窄屏结果导航](../apps/api/tests/test_result_browser.py) `pnpm test:browser`                   |

接口的任务状态、工作机阶段与输入类型可在 [API 契约](../apps/api/src/comfyshop_api/schemas.py) 核对。任务、执行、成品与作品的存储关系见 [数据库模型](../apps/api/src/comfyshop_api/models.py)。

## 代码中的单一定义

以下规则各只有一处实现，新代码应复用它们，文档其余部分描述的是这些规则的效果。

| 规则               | 位置                                                                                                                                                                          | 用法                                                                                                                        |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 任务与执行的状态值 | [`models.Status`](../apps/api/src/comfyshop_api/models.py)                                                                                                                    | 比较和赋值使用 `Status.QUEUED` 等常量，`Status.ACTIVE` 表示尚未结束。                                                       |
| 软删除             | [`models.SoftDelete`](../apps/api/src/comfyshop_api/models.py)                                                                                                                | 使用软删除的模型在常规查询中默认带上 `Model.visible()`，删除调用 `mark_deleted()`。需要读取已删除记录的查询在原处说明原因。 |
| 事务写锁           | [`db.write_lock`](../apps/api/src/comfyshop_api/db.py)                                                                                                                        | “先检查再写入”的操作先取得写锁。锁保留到事务提交或回滚。取得锁后重新读取状态，再判断能否写入。                              |
| 游标分页           | [`pagination.split_page`](../apps/api/src/comfyshop_api/pagination.py)                                                                                                        | 列表查询多取一行，由它切出本页和下一页游标。                                                                                |
| 按所有者读取       | [`security.owned_record`](../apps/api/src/comfyshop_api/security.py)                                                                                                          | 记录不存在与属于他人返回相同的 404。                                                                                        |
| 幂等重试           | [任务](../apps/api/src/comfyshop_api/services/tasks.py)、[成品](../apps/api/src/comfyshop_api/services/artifacts.py)、[作品](../apps/api/src/comfyshop_api/services/works.py) | 请求前和唯一约束冲突后使用同一个比对函数。                                                                                  |
| 浏览器请求         | [`createApiClient`](../packages/api-client/src/index.ts)                                                                                                                      | 路径模板、查询参数、请求体和返回类型取自生成的契约，接口变更会在类型检查时报错。                                            |
| 工作机本地记录     | [`WorkerState`](../integrations/comfyui/comfyshop_worker/config.py)                                                                                                           | `active.json` 记录当前租约、执行位置和回传进度。                                                                            |

路由函数只做参数解析、调用服务和组装响应，业务规则位于 `services/`。API 模块之间不互相导入。API 源码的函数参数必须标注类型，由 Pyright 检查。

运行 `pnpm api:generate` 同步网页 API 契约、分类选项和 Skill 的通用接口数据。[Skill 接口别名](../integrations/skills/comfyshop/operations.json) 记录命令名、对应的 OpenAPI 操作和特殊输出格式。生成后的接口数据随独立安装脚本分发。

## 数据路径

```text
Radix UI → TanStack Query → @comfyshop/api-client → FastAPI
FastAPI → SQLAlchemy → SQLite 或 PostgreSQL
FastAPI → 原文件存储 → 本地目录或 S3 兼容存储
```

开发时由 Vite 代理 `/api`；生产构建由 FastAPI 同时提供静态资源和 API。统一同源 Cookie，不使用跨站 Cookie、localStorage Token 或服务失败后的静态数据兜底。API 调用失败明确呈现错误及重试入口。

React Router 使用路径嵌套路由。个人页面共享登录边界，“我的”通过嵌套路由呈现各标签，任务详情由列表内的弹框打开。FastAPI 在处理 API 与静态资源后为页面路径提供 `index.html`。

「我的」和受邀人打开的共享空间复用同一组栏目路由与页面。共享空间读取请求带 `workspace_owner`，列表和详情使用 FastAPI 的空间读取依赖核对登录会话和账号级授权，再按空间所有者查询。新增栏目复用该读取依赖，现有授权即可生效。媒体 URL 按记录所属账号校验所有权、发布状态或空间授权。写入继续从真实登录会话取得账号，执行和修改沿用所有权校验。

个人和团队的「我的」共用 `/workspace` 入口和 `/workspace/<栏目>` 路由，工作机共用 `/machines`。页面按右上角选中的空间读取数据。旧版 `/workspace/teams/<id>` 链接在通过团队访问校验后进入对应栏目，保留查询参数和 URL 片段。团队列表、详情和版本读取传 `workspace_team`，React Query 按当前账号及空间保存缓存。`TeamReader` 检查会话、团队归档和成员资格。私有媒体地址按关联记录的空间查验成员资格，公开作品的成品和参考素材按发布清单读取。

页头的账号菜单控制当前空间。浏览器标签页保存所选团队的导航偏好，团队资料、角色和权限由服务端会话和成员资格确定。公开工作流库读取全局公开列表，卡片和收藏页使用当前空间的收藏状态。团队收藏开放本团队工作流及公共库工作流，访问公共工作流时按发布版本检查可见性。

工作流、素材、工作机、任务和作品的 `team_id` 表示团队归属，`owner_id` 在团队记录上保留实际操作者。执行及成品沿用任务归属。团队导入和上传使用 `/api/v1/teams/<id>` 路径，工作机、生成、结果管理和发布沿用个人路由并传 `workspace_team`。在会话和 CSRF 校验后锁定团队行并读取当前角色，内容变更和 `team_events` 的操作者记录在同一事务保存。个人和共享空间按账号读取，公共库按发布状态读取个人及仍在使用的团队内容。团队素材配额按团队计算，并在团队内按原件去重。成员移除与账号注销保留团队记录，所有权转让在同一事务切换唯一的 Owner。

`GET /api/v1/teams/{team_id}/events` 校验管理员及以上角色，从同一份事件表按时间和 ID 倒序分页。操作者搜索匹配昵称或账号名，日期筛选使用浏览器本地日期对应的毫秒区间。对象名称从日志关联的空间和仍可见的公开工作流解析，无法解析时保留对象编号供追溯。

结果组和放大的成品各占一条浏览器历史记录。同层切换更新当前记录，站内关闭和浏览器后退依次回到同组的成品列表和来源结果列表。列表保持当前筛选和已读取的分页，关闭预览时恢复滚动位置与原卡片焦点。

应用继续通过 `@comfyshop/ui` 和 `@comfyshop/media` 组合界面，Tokens 为样式唯一来源。所有媒体集合使用 Masonic：窗口与弹框滚动均归一化到列表坐标；追加保持测量缓存，重排、替换或删除索引时重建缓存。公开、个人与收藏库共用一套分页组件。任务历史按游标加载，可用 `state` 参数按状态筛选，列表项带代表成品。运行期间每 2 秒通过 `/tasks/activity` 刷新活动任务的状态。历史页上的活动任务结束后，按 ID 读取一次详情并更新显示。任务离开活动集合时刷新该账号相应工作流的状态筛选，进行中列表立即移除终态任务；未筛选的历史分页继续保留。当前筛选下的完成执行数变化时刷新对应的结果缓存，保留已加载页数。组件、Context 和 Hook 分开导出，避免开发热更新上下文不一致。

## 工作机接入与任务分派

工作机定义的注册入口是 `services/worker_types.py` 的 `WORKERS`。定义声明连接归属、可用站点、工作流结构、输入输出类型、执行适配器及可选的取消能力。工作流版本携带工作机类型和站点，任务保存最终选用的工作机和服务类型。网页从 API 返回的定义构建连接操作和生成表单。[平台注册表](../apps/api/src/comfyshop_api/services/worker_types.py) · [公共协议](../libs/worker-protocol/comfyshop_worker_protocol/definition.py)

| 连接归属   | 选择与凭据                                           | 执行                                                     |
| ---------- | ---------------------------------------------------- | -------------------------------------------------------- |
| `machine`  | 在当前空间的匹配工作机中选择，工作机持平台签发的密钥 | 已发布的 ComfyUI 客户端领取本机队列，执行冻结的节点图    |
| `account`  | 每条具名连接归当前空间，版本要求相同类型和站点       | 独立服务领取对应类型的任务，用当次租约取回所选连接的凭据 |
| `platform` | 部署方管理凭据并提供服务，生成表单自动分派           | 平台服务按执行适配器领取任务，并可接管过期租约           |

ComfyUI 工作机在个人或团队空间接入。接入申请经确认后记录操作者和目标空间，兑换与重新连接使用同一归属，团队的默认工作机独立保存。团队成员可读工作机状态，管理员和所有者可以管理。团队归档后该团队的工作机密钥停止认证。读取表单和提交时，服务端核对当前空间的工作机、版本、素材及重跑来源；幂等提交按操作者与空间处理。工作机按分配的工作机 ID 和空间领取任务，素材和成品请求沿用同一份租约校验。

管理员和所有者用现有的发布接口发布当前团队的工作流及作品。工作流验证同空间的成功执行，作品复用公开版本、成品清单和参数选择校验。公共媒体授权以实际选中的成品和作品参考素材为准，团队归档时同时停止公开。

个人和团队的云端连接共用工作机表，Key 使用 Fernet 加密。外部工作流按空间和上游标识归并，导入在云端读取结束后重新校验会话、团队编辑权限和连接版本。任务保存当次连接的名称与凭据版本，工作机用有效租约在任务所属空间读取该连接的凭据。更换 Key 后使用原凭据版本的任务仍可追溯。重新提交能选择新的计费连接，补跑继续校验原连接。

三类工作机的协议客户端统一记录领取、续租、重试和成品回传。运行时使用同一份 Loguru 配置，任务和执行的日志上下文跟随异步任务。日志目录和级别见[工作机日志](deployment.md#工作机日志)。[协议客户端](../libs/worker-protocol/comfyshop_worker_protocol/platform.py) · [日志配置](../libs/worker-protocol/comfyshop_worker_protocol/logging.py)

### 新增工作机

1. 在独立的 `integrations/<名称>-worker/` 包中声明 `WorkerDefinition`。个人云端服务使用 `connection="account"`，列出站点，并实现 `load_reference(scope, key, reference)`。返回的 `Source` 保存稳定引用及工作流。节点图使用 `form="nodes"` 和归一化的节点目录。命名字段使用 `form="fields"`，返回 `FieldWorkflow` 的字段与执行描述。设置支持的 `input_kinds`、`output_kinds` 及成品节点。平台托管的字段工作流可由 `COMFYSHOP_OFFICIAL_OWNER` 指定的维护账号或其授权的作者导入 `format="service"`、`workerKind` 指向注册类型的清单。
2. 在定义的 `executor` 中提供执行适配器工厂。工厂接收 HTTP 客户端和本次连接的凭据。`prepare` 处理输入和素材，`submit` 返回已受理的云端 ID，`poll` 返回云端阶段或成品列表，`download` 写入原件并返回文件名和来源节点。如服务确认在创建任务前拒绝请求，可抛出 `SubmissionRejected`。需要远端取消时实现 `cancel`。`prepare` 收到的任务中，`task.inputValues` 按表单字段 ID 保存冻结值，`assets` 记录素材对应的节点和输入名。个人云端工作流的 `workerContext` 给出远端引用、版本摘要及字段到节点的映射。共用的 `ServiceRunner` 负责领取、续租、保存回执、回传原件和确认执行完成。[执行协议](../libs/worker-protocol/comfyshop_worker_protocol/service.py)
3. 将包加入平台依赖，在 `WORKERS` 中注册一次，并在 `COMFYSHOP_WORKER_SERVICE_TOKENS` 按类型配置独立服务令牌（JSON 对象），也可按类型设置 `COMFYSHOP_WORKER_SERVICE_TOKENS__<类型>`。每个工作机进程仅接收自身令牌。执行进程加载同一份定义，使用对应令牌连接平台并运行 `ServiceRunner`。三种工作机通过协议库的 `Platform` 领取任务、续租、校验素材和回传成品。ComfyUI 将领取凭据保存在状态目录的 `active.json` 中，官方工作机按执行次数控制并发，RunningHub 通过 `ServiceRunner` 调度适配器。工作机类型匹配、参数编辑、提交、状态、结果和作品发布由平台注册表和已有字段模型驱动。[RunningHub 接入示例](../integrations/runninghub-worker/README.md)

## 展示语言

[语言清单](../apps/api/src/comfyshop_api/core/languages.json)由 FastAPI 和 Web 共用。FastAPI 依次采用有效的 `comfyshop.language` Cookie、按权重匹配的 `Accept-Language`、部署的默认语言。FastAPI 将解析结果写入 HTML 的 `lang` 及启动数据，Vite 开发服务器通过 `/api/v1/presentation` 获取同样的数据。页头语言菜单记住手动选择，刷新同一路径并保留查询参数及片段。

简体中文、台湾繁体中文、英文、日文和韩文使用同一个域名及路由。工作流链接为 `/workflows/<id>`。作品和历史版本分别通过 `?work=` 和 `?version=` 定位。工作机接入和 Skill 安装分别使用 `/machines/link` 和 `/skill`。

公开目录为各语言共用。个人目录、任务、执行、资产、成品和收藏按账号读取，访问范围由所有权、发布状态及历史执行记录决定。媒体链接在读取时执行同一套权限判断。RunningHub 等个人云服务继续按其连接保存供应商区域及密钥。

新增展示语言时更新清单，补齐 [Web 语言包](../apps/web/src/app/locales/) 和 [API 语言包](../apps/api/src/comfyshop_api/core/locales/)，在 [Web 翻译入口](../apps/web/src/app/i18n.ts)登记新语言包。前后端各语言包保留相同的稳定键和插值参数。API 按请求语言显示平台错误、邮件和语言包已收录的工作机提示。作者文本、供应商详情和其他诊断保留原文。

## 服务端

### 应用与路由

`create_app(settings)` 管理生命周期与独立 Engine，`get_db` 为每个请求提供 Session。路由位于 `api/`，工作流规则位于 `services/`；Pydantic 定义输入输出，不直接返回数据库用户对象。OpenAPI 的错误响应与实际返回的简短 `detail` 一致，校验错误不回显密码或整份工作流。

### 数据库

数据库保存账号、会话、工作流、版本、收藏、工作机、任务、执行、素材、成品与作品。Alembic 管理表结构；应用不通过 `create_all` 重建表。版本 JSON 和 SHA-256 哈希固定，任务引用版本外键并保存参数及名称快照。归档工作流不会删除历史任务或版本。图数据延迟读取，列表不会加载整份原始 JSON。

[媒体模块](../libs/media/) 是独立的 `comfyshop-media` Python 包，ComfyShop API 通过 uv workspace 依赖它。独立 Python 库放在 `libs/<name>/`，各自声明依赖，可用 `uv build --package comfyshop-media` 等命令单独打包。

`libs/media` 接收字节流，在数据卷的 `staging/` 暂存并校验内容，提供本地和 S3 存储、缩略图及视频处理。本地存储在同一文件系统上用硬链接原子发布已校验的文件。API 管理 `media_objects` 登记和素材、成品的业务引用。素材、成品和作品引用各自保留文件名与 MIME，通过 SHA-256 外键复用同一份原件。并发上传由数据库选定使用的原件，每次写入使用独立存储名。写原件前先持久登记候选名，选中的候选与业务引用在同一事务内移出回收队列。进程中断后，维护循环取得暂存目录的文件锁，再将未确认的候选交给回收。

业务路由核对素材所有权、任务租约或作品可见性后读取媒体，由 API 生成 HTTP 响应。对象桶保持私有，S3 原视频的单段 Range 从对象存储按段流式返回。原件回收循环核对素材、成品、作品输入、执行封面、作品封面、工作流上传封面和模型默认图的外键。软删除记录仍持有外键。后台事务将无引用原件的存储名登记到回收队列，再在数据库事务外删除文件，失败时重试。原件回收与工作机租约维护分别运行。

### 时间与分页

时间统一保存为 UTC Unix 毫秒，界面在本地显示。SQLite 使用 WAL、外键和连接等待超时。查询以时间与唯一 ID 为稳定顺序，游标使用键集分页；插入新任务不会导致已浏览分页出现重复或遗漏。

## 身份与权限

密码采用 FastAPI 官方文档推荐的 [pwdlib/Argon2](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)。本项目的浏览器认证使用可撤销的不透明会话；数据库仅保存会话 Cookie 的 SHA-256 哈希，原始 Cookie 只由浏览器以 HttpOnly、SameSite=Lax 保存。会话到期或退出后不可复用。通过 Origin 与 CSRF Header 保护写操作；认证频率计数持久化，重启不会重置。登录错误不区分账号不存在和密码错误。

修改密码、绑定邮箱和注销都要再次核对当前密码。修改密码会撤销其他会话，重置密码会撤销全部会话。两者都会撤销所有工作机并作废待兑换的接入申请。恢复 ComfyUI 工作机时，在「工作机」重置密钥并下载新配置。恢复 RunningHub 时，重新添加连接。找回密码的凭据只以 SHA-256 保存，默认 30 分钟有效，使用一次即失效；申请接口对绑定和未绑定的邮箱返回相同响应，邮件在响应之后发送，并按来源地址和邮箱计入频率限制。未配置邮件服务时，邮件内容写入服务日志。绑定邮箱要经过确认邮件：注册或在账号设置里填写的邮箱先记为等待确认，确认凭据只以 SHA-256 保存，默认 24 小时有效（由 `COMFYSHOP_EMAIL_CONFIRM_TTL_SECONDS` 配置），使用一次即失效，重新填写、修改或重置密码、注销都会让它作废。确认接口不要求登录，由用户在弹框里点击后提交，确认后邮箱才写入账号并用于找回密码，按旧邮箱发出的重置凭据随之作废。邮箱在账号之间唯一，是否已被绑定只在确认时判断，注册和填写的响应不透露。确认邮件与重置邮件一样只使用 `COMFYSHOP_PUBLIC_URL`，发信但未配置该地址时填写邮箱返回 503；每次填写按账号和来源地址计入频率限制。此前已经绑定的邮箱保持有效。注销按软删除的约定隐藏该账号的工作流、作品、任务和成品，撤销工作机并结束进行中的任务，清除会话、收藏、邮箱和密码，账号名改为内部占位值后可重新注册，显示名「已注销」保留，新账号不能使用；用户行保留以维持其他记录的引用。

重置邮件链接只取自 `COMFYSHOP_PUBLIC_URL`，不信任请求的 Host；发信但未配置该地址时申请重置返回 503。不发信时链接只写入服务日志，未配置地址时给出站内路径，请求的 Host 不会进入日志里的链接。登录和敏感账号操作按账号和来源地址限制错误次数：每次核对先计数，超过上限返回 429，核对成功后退回这次计数，正确密码本身不计入次数。按账号的计数不区分来源，10 分钟内错误 10 次后，这个账号在窗口结束前即使输入正确密码也返回 429。来源地址只接受合法 IP，IPv6 按 /64 网段计数。注册、申请重置和工作机接入申请按次数计。计数窗口为 10 分钟，过期记录由后台删除。敏感账号操作在锁外核对密码哈希，再取得账号写锁并确认密码在核对期间未被修改；SQLite 的写锁覆盖全库，核对和生成密码哈希（改密码的新密码、重置密码、注销时的占位密码）都在锁外完成；重置密码先确认凭据有效再计算哈希，无效链接不触发哈希计算。注册先判断账号名再判断邮箱，并发注册在唯一约束上失败时按同样的顺序给出冲突原因。重置凭据在同一锁内重新检查并消费；并发使用同一凭据最多一次成功。绑定或解除绑定的邮箱时撤销旧凭据。

客户端只在内存中持有 CSRF 值。TanStack Query 缓存以用户 ID 隔离；登录切换、退出和 401 会取消请求并移除原身份的数据。服务端始终按当前会话校验记录所有者，不能用请求中的用户 ID 提升权限。无管理员角色。

昵称与头像是独立于登录账号名的资料。资料写入沿用会话与 CSRF 校验，并在账号锁内复核会话。头像上传在锁外核对字节大小和图片尺寸，依 EXIF 方向居中裁切后只存重新编码的 256 × 256 WebP，随数据库一起备份。替换或移除头像后旧地址失效，注销同时清除昵称和头像。作者资料与头像可由本人查看，有公开工作流或作品时也向访客开放。团队成员可在名单中查看同一活跃团队成员的昵称和头像。读取头像时先核对可见性，再处理浏览器缓存验证。

HTTP 部署的 Secure Cookie 默认为关闭；部署 HTTPS 时通过 `COMFYSHOP_COOKIE_SECURE=true` 开启，并配置允许的 Host、Origin。服务地址与认证配置由部署环境提供，客户端使用相对路径访问同源 API。

生产与开发启动命令默认绑定 `0.0.0.0`，允许通过服务器实际 IP 访问。默认 Host 配置为 `['*']`，可通过 `COMFYSHOP_ALLOWED_HOSTS` 覆盖为明确的 IP 或域名列表。写请求仍检查同源 Origin 与 CSRF；不将允许的 Origin 改为通配符。Vite 的 `/api` 代理保留来访 Host，使局域网开发页面继续以同源 Cookie 登录。

## 项目

项目归属个人或团队，读取沿用空间鉴权，写入沿用账号或团队锁及角色判断。项目详情复用空间的结果、作品、任务和资产库列表。列表按空间和项目过滤后再分页。工作流、素材通过关联表加入项目，继续使用原记录的读权限和生命周期。

项目列表对当前页批量查找预览，优先选同一空间内最近成功执行的可见图像或视频，其次选已关联的图像或视频素材。卡片复用原有缩略图接口和媒体访问权限。

每个任务最多归属一个项目。结果从其来源任务取得项目，作品通过来源执行归集。调整项目只更新任务行，随即反映到整批执行及其作品。只可将新任务和资料归入进行中的项目，补跑和载入历史参数也只沿用当前空间中进行中的来源项目。公开作品接口只使用作品的发布范围。

归档项目保留详情、关联和已有任务，列表按归档状态筛选后再分页。删除项目沿用软删除标记，隐藏项目和按项目过滤的入口，普通空间列表继续读取各自的记录。撤销删除清除删除标记，原有归档状态及现存关联随项目恢复。项目变更与团队操作记录使用同一事务。

## 工作流与任务

### 工作流版本与发布

导入验证 ComfyUI API/界面 JSON，限制大小并记录图格式、哈希和节点依赖。完整图保存在不可变版本中。表单的默认输入由版本图与工作机节点定义共同生成，未识别的自定义节点仍保留原始数据。作者手动发布需要该版本的成功执行记录。工作流分别保存最新草稿和已发布版本指针，版本记录保留发布状态；新增草稿不会撤回已公开版本、作品或媒体。公共列表读取已发布版本，作者的个人列表读取最新草稿。详情的版本切换向访客列出已发布版本，向作者同时列出草稿。作品列表在分页前按所选版本过滤。作者页的公开作品使用来源工作流的当前发布版本过滤。作品链接按作品记录的版本打开详情。

### 任务提交与取消

官方工作流的 `POST /api/v1/tasks/cost-estimate` 与生成共用工作流版本、表单哈希、来源和输入校验。应用读取当前空间或作品分享范围内授权的原件，将报价请求发给内网官方工作机。工作机按 `execution.adapter` 选择报价函数，返回十进制单次金额、币种和按用量估算标志。报价使用执行所用的供应商账号，Atlas Cloud 的请求参数及素材映射和实际生成共用实现。网页按执行次数计算本批费用。

新增官方供应商时，在官方工作机启动处按执行适配器注册报价函数，复用同一入口和响应格式。见 [官方工作机配置](deployment.md#官方工作机) 和 [用量估算扩展](usage-estimates.md)。

任务创建使用“账号 + 幂等键”唯一约束。同键同参数返回原任务，同键不同参数拒绝；唯一约束处理并发重复提交。排队和执行中的任务都可取消，取消、恢复排队和删除记录先取得任务写锁再读取状态，与工作机的领取、续期和完成串行：取消执行中的任务会释放工作机占用，工作机的下一次任务请求收到 HTTP 409 和协议错误码 `task_cancelled`，据此停止跟踪，并按自己提交的 `prompt_id` 请求停止任务。任务状态、进度及完成结果由 API 和获得有效租约的工作机写入。

撤销取消仅适用于未被领取且未删除的任务。恢复前检查工作机仍可用且任务引用的素材仍保留，通过后按原提交顺序回到队列。删除任务记录的撤销独立处理，恢复时重新核对引用素材占用的配额。

### 浏览器任务通知

账号菜单里的生成完成通知按登录设备开启，订阅绑定当前登录会话。退出、切换账号或会话到期后，服务端停止投递。个人和团队任务都向实际提交者的设备投递。团队任务在投递时仍会核对团队成员资格，打开通知后继续走现有任务详情的访问校验。

工作机完成整个任务时，服务端在同一事务中记录待投递通知。维护循环领取并加密发送，推送服务暂时不可用时重试，过期订阅会被删除。发送到系统通知栏的文字使用通用文案。服务工作线程接收通知并打开对应任务地址。

默认启用浏览器通知能力，由用户主动订阅。数据目录持久保存 `web-push-key.pem`，更新镜像时沿用同一个数据卷。多进程或多实例共用数据库时也需共用通知密钥。可用 `COMFYSHOP_WEB_PUSH_ENABLED=false` 关闭能力，或通过 `COMFYSHOP_WEB_PUSH_CONTACT` 设置 HTTPS 联系地址或管理员邮箱。推送由服务端通过 HTTPS 发送给浏览器的推送服务。

### 工作机身份

任务引用指定的自有工作机。机器密钥以 Bearer 提供，数据库只保存 SHA-256；浏览器会话和密钥接口的权限分开。机器密钥不能访问用户的浏览器接口，也不能领取其他机器或其他账户的任务。选择默认机器持久化在用户偏好中。

工作机启动时没有密钥便会申请接入。申请有效期为 10 分钟。工作机自行保存原始凭据，把只含接入代码的确认页地址交给浏览器。确认页显示申请时间和来源地址，比较两边的来源并在结果不同时提示核对（IPv4 比较地址，IPv6 比较 /64 网段，地址未知或协议族不同时不提示）。登录账号可给新增工作机命名，也可指定本账号未撤销、离线且空闲的工作机重新连接。兑换时平台新建工作机或为所选工作机换发密钥，后一种方式沿用工作机 ID、名称、默认设置及排队任务。确认后的进度仅对确认账号可见。网页等待期间轮询此申请，密钥兑换后显示已接入并更新工作机列表。打开列表或切回所在标签页时立即读取当前空间的工作机，列表在前台时每 2 秒刷新连接状态。

换取的回复丢失时，工作机在申请到期前凭同一凭据重试，平台为同一台工作机换发密钥，丢失的那份随之失效，不会留下多出的工作机。只有工作机还没用密钥连上平台时才允许重试；用户在网页重置或撤销密钥时删除指向它的申请，工作机已被撤销时也不能再换取。确认接入时在账号锁内复核发起确认的会话。申请和换取两个入口不需要登录；申请按来源地址限制频率，等待中的申请另有全平台数量上限。平台不保存原始凭据和原始密钥。启动包由平台在下载时写入自己的地址，配置了 `COMFYSHOP_PUBLIC_URL` 时使用它，否则取请求的地址。重置密钥只结束执行中的任务（旧密钥持有的租约无法再回传），排队任务继续等待这台工作机；撤销同时结束排队任务。已认证的领取请求在密钥被重置后不能领到任务。

接入确认通过条件更新只允许一个账号绑定申请。兑换在账号写锁内重新检查申请，并在创建工作机或为原工作机换发密钥的同一事务中记下工作机。重新连接时在工作机锁内复核在线和占用状态，过期或并发作废的申请无法兑换。重置、撤销或重新连接工作机会作废指向它的其他申请；心跳写入时复核密钥。

### 领取与租约

新任务提交时使用与工作机列表相同的规则核对所选工作机在线。在线但忙碌或暂停接单的工作机仍可接收排队任务。工作机掉线后，已入队任务继续等待原工作机。重复提交同一已受理的请求仍返回原任务。

队列按 `queued_at` 和任务 ID 排序。任务详情使用同样的顺序统计前方排队任务。`PUT /tasks/{task_id}/machine` 在账号锁内确认目标机归属和在线状态，再锁定任务核对尚未领取，校验目标机能使用冻结的执行图和输入。换机更新分配和入队时间。领取写入同时核对任务状态和工作机归属。

工作机的暂停接单设置保存在 `machines.paused`。修改设置和新领取使用同一工作机行锁。暂停期间新领取返回 `null`，已有领取仍可按原租约恢复、续期及回传。恢复接单沿用原任务分配和排队顺序。

领取同时锁定机器容量和排队任务。领取编号与租约凭据由工作机先持久化，同一次领取重试返回原任务。进度事件以单调序号处理，有效租约才能更新任务。后台以 15 秒间隔处理过期租约，工作机领取时也执行清理；清理先按状态与租约时间的索引只读查找，没有到期任务时不写入。未回传完整清单的过期任务标记失败，已确认全部执行清单的遗留任务补记成功。任务列表、任务详情、活动状态与工作机列表读取已提交的状态。工作机遇到单条租约失效时结束当前跟踪，等 ComfyUI 空闲后继续领取。密钥失效时停止接单。暂时性故障（包括平台 5xx 和代理返回的网页）按逐次加倍的间隔重试，有进展时重新计时；持续出错且没有进展超过 15 分钟，或遇到未预料的错误时回报任务失败，工作机继续运行。回报失败期间继续续租。机器心跳与任务心跳分开处理，前者失败不影响租约续期。

### 任务详情

任务详情通过 `/tasks/{task_id}/progress` 读取当前任务及各次执行的状态，只在打开的详情中轮询活动任务。`/tasks/{task_id}/inputs` 根据任务提交时的快照提供字段名称、版本和已绑定素材，用于展示提交输入及单次执行的实际输入。两个接口均只允许任务所有者读取。

失败或停止的批次在详情打开时继续轮询待核对或补传中的执行，直到有结果或核对窗口结束。`POST /tasks/{task_id}/retry-executions` 在任务锁下按所选执行序号复用其冻结参数和种子，生成一条独立排队任务。原执行记下对应补跑任务。相同幂等请求返回原补跑任务。

### 工作机版本与更新

工作机在心跳请求体的 `runtime` 中上报程序版本和更新能力。程序版本来自安装包或项目元数据，签名启动包的 `worker-build.json` 还包含构建标识。带发布公钥的启动器负责自更新。

`operatingSystem` 上报工作机系统，可取 `windows`、`macos`、`linux`，其他系统填 `null`。平台保存最近一次上报值，离线和换发密钥后也可查看。`comfyStatus` 上报本机 ComfyUI 队列空闲、占用或不可达，首次探测完成前可为空。ComfyUI 探测有独立超时，节点目录写入成功时记录同步时间。

`startupIssue` 上报启动时的连接或同步问题，平台记录最近一次诊断及收到的时间。独立启动包通过 Windows 任务计划程序、macOS LaunchAgent 或 Linux systemd 用户服务启动同一个入口。系统进程管理器负责异常重启，工作机状态目录的锁和恢复记录继续约束领取与恢复。后台日志滚动保存在状态目录。

`machines.runtime_info` 保存最后一次上报的版本。`machines.update_info` 记录更新状态，工作机交付当前任务后才绑定最新签名发布包。排队更新后允许恢复原来的领取，新的任务继续排队。更新开始时用工作机行锁复核密钥、任务占用和最新发布包。

平台发布目录只保留最新签名包。下载前若发布已切换，平台在工作机行锁内重新排队并返回 410。启动器先恢复本机原版，原版通过心跳接收新的更新请求。启动器校验签名、大小与摘要，将新版与锁定的依赖装入独立目录，并用原连接配置完成就绪检查。就绪后原子写入版本指针。校验、安装或就绪失败时由原版心跳报告，工作机按接单设置继续领取。

### 工作机执行

官方工作流使用现有的工作流导入和发布流程。维护账号与获授权的账号从网页上传服务清单，平台按全局唯一的清单标识查找工作流。首次导入的草稿归导入人管理，后续只有其作者可以更新该条目。官方工作机凭据调用同一接口时使用配置的维护账号。Compose 的 `official-init` 按需创建维护账号，默认将内置工作流保存为该账号的草稿。官方工作流在生成时读取该版本保存的表单和配置，并固定派发到官方队列。个人和团队从同一表单提交已发布的版本，素材和任务按当前空间校验和保存。页面呈现生成参数、状态和成品，省去工作机选择。

官方工作机由 `integrations/official-worker` 独立运行。它通过 `POST /api/v1/worker/services/official/claim` 从官方队列领取任务，与个人工作机共用续租、素材读取、成品回传和完成接口。模型请求映射、Atlas 素材上传及生成均在官方工作机执行。平台保存用于续查的生成编号与提交状态。租约接管后能查询原任务，提交结果不明确时状态为待核对。取消官方任务会结束平台任务和回传，已提交的上游生成仍由供应商处理。

官方工作机按单次执行分配实例的并发名额，各任务共用同一上限，每个任务独立续租并汇总执行进度。单次执行失败时，工作机立即调用该执行的失败接口，平台保存失败状态与补跑资格。已开始的其他执行可继续回传成功清单。租约接管后，工作机会续查已受理的预测并保留此前确认的成功和失败结果。

官方工作机申请领取任务时，平台按请求声明的适配器记录最近接单时间，空队列也会记录。排队详情跨账号统计同一适配器下排在本任务之前的可领取任务，按入队时间、任务 ID 排序。有效租约用于提示已有官方工作机在执行任务。没有有效租约时，最近 45 秒内有接单请求就提示等待领取，超过该窗口或尚无记录则提示近期未收到接单请求。其他账号的任务只计入前方总数。

官方工作机领取租约已到期的执行中任务时，平台在发放新租约的同一事务内记录接管。任务进度接口按服务端时间判断当前租约是否到期。到期时 `officialTakeover` 为 `waiting`，接管后的有效租约返回 `resumed`，首次领取和已结束的任务返回空值。工作机续租会更新执行阶段，网页同时显示接管提示和最新阶段。

任务详情通过进度接口的 `include_takeover_history=true` 读取接管记录。平台在同一任务写锁和事务内，以旧租约到期时间为起点，保存每段已结束等待的序号、结束时间与结果。尚未接手时，进度接口按服务端当前时间计算本段时长。读取已结束记录时以进度快照中的最后一个序号为界。

Atlas 适配器通过 `execution.config.media` 将已上传的表单素材映射到请求字段。数组按声明的槽位顺序组装，随后追加工作流允许的外部素材链接或 Base64。素材与生成数量的组合上限计入全部来源，在提交前校验。`execution.outputKind` 声明主成品类型，`additionalOutputKinds` 声明同一次执行可接收的附加媒体类型。[组图编辑示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v5.0-lite/edit-sequential/README.md) · [视频与尾帧示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedance-2.5-flash/text-to-video/README.md)

需要混合素材对象数组的 Atlas 参数在 `execution.config.media` 中声明 `groups`。工作机按分组和槽位顺序上传素材，将 URL 与实际媒体类型组合为 `{url, type}` 对象，可校验总数和至少需要的一种素材类型。[混合素材示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/h3-max/reference-to-video/README.md)

音色、录音与图像可通过 `reference_arrays` 组装为顺序固定的参考对象。每槽选择单一来源，随后按槽位配置使用上传链接或内联 Base64。[参考音频示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seed-audio-1.0/README.md)

多视图重建模型可使用 `media_bitmask` 声明位置编码对应的素材参数，工作机在提交前校验编码长度及多图数量。预计耗时较长的模型可通过 `prediction_timeout_seconds` 调整轮询时限，默认为 30 分钟。[多视图示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/hi3d/v3.0-master/image-to-3d/README.md)

Atlas 接口开启 `enable_base64_output` 后，工作机可以直接解码预测中的成品。图像接口默认解码图像，返回 ZIP 的模型声明 `base64_output_format: "zip"`。音频接口按请求格式解码 MP3、WAV 或 PCM。解码原件与从 HTTPS 下载的成品使用相同的回传和校验流程。[文生图示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v4.7/text-to-image/README.md) · [3D 归档示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seed3d-v2.0/image-to-3d/README.md) · [音乐示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/music-3.0/README.md)

Atlas 图像请求开启 `enable_sync_mode` 后，可以在提交响应中获得成品。工作机先保存预测编号，再处理成品。接管现有执行时从该编号续查。工作流可声明提示词长度、图像宽高、总像素和比例范围，并按接口限制配置是否接受自动尺寸及其依赖的参数。[同步图像请求示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/h3-image/text-to-image/README.md) · [自定义宽高示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v4/README.md)

模型 Schema 指定 `result` 时，工作机按该地址轮询。接口返回 404 或 405 时，用同一编号查询 `prediction`。工作流可按缩放模式筛选倍数或尺寸字段，或按选定模板校验数值范围。[图片超分示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/tencent/image/upscaler/README.md) · [视频超分示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/tencent/video/upscaler/README.md)

语音转写工作流将 `execution.outputKind` 设为 `text`。工作机把转写正文保存为 UTF-8 文本，将供应商提供的结构化转写保存为 JSON。两种成品沿用现有的输出权限、预览和原件下载。工作流可以约束音频格式与请求选项一致，并校验以字符串传入的 JSON 参数。[转写示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seed-asr-2.0/README.md)

歌词生成沿用文本成品类型。正文保留可直接复制的段落标签，歌曲标题和风格等信息同时保存在结构化 JSON 中。[歌词示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/lyrics-generation/README.md)

官方工作流的素材字段可用 `additionalAssetKinds` 声明兼容类型。参数表单和任务提交使用同一份约定，例如转写同时接受音频或含音轨的视频。Atlas 参数可把逐行输入转换成文本数组，并在满足指定条件时要求填写关联参数。[素材兼容和条件参数示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/xai/stt-v1/README.md)

官方文本字段可声明 `maxLength` 以接受较长的结构化文本。分段音乐方案在表单中编辑为 JSON，工作机校验段落数量、内容和总时长，再发送为结构化对象。[分段方案示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/elevenlabs/music-v2.5/text-to-music/README.md)

官方工作流的 `WorkflowVersion.translations` 保存按语言索引的标题、简介、字段标签、选项文案和参数帮助。服务清单按稳定标识同步一份执行定义。表单先计算执行定义的哈希，再应用译文。语言切换或单独同步译文时复用原版本和表单哈希。官方枚举字段用 `choiceLabels` 提供显示文案，任务保存和提交实际选项值。Atlas 工作机可按选项校验关联参数，例如预设音色对应的语言代码。[音色示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/elevenlabs/v3/text-to-speech/README.md)

多音色对话可以用 JSON 数组编辑逐轮台词和音色。工作机保留顺序并校验音色数量及总字符数，按选定格式保存裸音频原件。[对话示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/elevenlabs/v4/text-to-speech/README.md)

音色与语言可以按 Schema 联动。设为自动检测时，工作机为语言受限的音色填入所需语言。手动指定时校验语言与音色的组合。只接收一种语言的提示数组可绑定到枚举字段，由工作机将选中的语言放入单项数组。[音色与语言示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/xai/tts-v1/README.md) · [语言提示示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/qwen-audio-3.1-tts-plus/text-to-speech/README.md)

创建音色可接收一份上传素材或已有的供应商视频 ID。工作机在提交前校验来源和已识别的素材时长，生成后保存试听音频、文本音色 ID 和 JSON 详情。[音色创建示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/kwaivgi/kling-v4.0/custom-voice/README.md)

在附加成品类型中声明 `text` 时，Atlas 工作机也会回传供应商 `files` 中的 `METADATA` 项，保留 JSON 原件。[音乐元数据示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/elevenlabs/music-v2.5/text-to-music-detailed/README.md)

音频工作流可在附加成品类型中声明 `image`，由工作机将 `outputs` 提供的音轨与 `thumbnail` 提供的歌曲封面一起保存。[歌曲封面示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/suno/chirp-v6/README.md)

图像素材绑定可以声明单张字节上限、边长范围、总像素上限和长短边比例。工作机使用平台已识别的原件信息完成校验。素材可通过供应商上传接口转换为 URL，也可按工作流配置以内联 Base64 地址提交。[参考图限制示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/h3-image/edit/README.md) · [Base64 素材示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/tencent/hunyuan3d-rapid/image-to-3d/README.md)

图像素材数组还可接收逐行填写的公开图片地址或 Base64 data URL。工作机按上传槽位和文字输入的顺序组装素材，校验合计数量。透明图像编辑可要求 PNG 输出和单张含透明通道的参考图，工作机校验已上传或内联的原件。[透明图片编辑示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v5.0-pro/edit/README.md)

图层拆分可绑定单张上传原图或一个图片地址。工作机按供应商给出的顺序保存底图与透明图层，并将 `layers` 里的位置和叠放顺序保存为 JSON 成品。[图层拆分示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v5.0-pro/layer-decomposition/README.md)

图像工作流声明附加文本成品后，工作机也会保存 Atlas 返回的 `image_results`，其中的实际背景类型按索引与图片成品对应。PNG 原件保留 Alpha 通道。[透明图片示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/bytedance/seedream-v5.5/text-to-image/README.md)

图像接口可返回动画 GIF 或 SVG 矢量原件。GIF 沿用图像成品流程并保留全部帧。SVG 按有效的 UTF-8 XML 文件验收，在界面按文本预览，原件以附件形式下载。工作机按输出格式选择请求字段，并校验格式、背景、数量及自定义尺寸间的限制。[GIF 与 SVG 示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/openai/gpt-image-2.6-sunburst/text-to-image/README.md)

图像编辑接口可声明支持 Atlas 素材库的 `asset://` 引用。蒙版和标注绑定为独立素材，工作机检查 PNG 透明通道、素材互斥关系和输出格式限制。[蒙版与标注示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/openai/gpt-image-2.6-sunburst/edit/README.md)

图片接口仅接收 URL 时，工作机将上传图转换成 Atlas 素材地址，并校验手工输入的 HTTP(S) 地址格式。Atlas 检查素材是否可访问。[URL 素材示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/nano-banana-2/edit/README.md)

参考视频生图支持上传原视频或采用公开地址。工作机将地址、起止秒数和采样帧率发到 `video_clips` 数组，可以同时提交参考图片。[参考视频生图示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/nano-banana-2.1/reference-to-image/README.md)

参考素材生成视频可声明图片或短视频至少提供一种，两种可同时提交。工作机检查 MP4 上传素材的时长，分别按提交顺序组装图片和视频数组。[参考生视频示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/gemini-omni-1.1-flash/reference-to-video/README.md)

图生视频可随素材限定时长。Gemini Omni 1.2 Flash 单独使用起始帧时最长 15 秒。提供结束帧时最长 10 秒，工作机统一校验上传、URL 和 Base64 素材。[图生视频示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/gemini-omni-1.2-flash/image-to-video/README.md)

Gemini Omni 1.2 Flash 参考生视频生成 11 至 15 秒成品时最多接收一段参考视频。工作机合计上传视频和手工填写的地址，校验数量与时长。[多素材时长示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/gemini-omni-1.2-flash/reference-to-video/README.md)

Gemini Omni Flash Developer 的参考生视频从一段原视频选取最多 10 秒。工作机以 `url`、`start` 和 `ends` 组装视频对象，校验剪辑起止时间，另外提交选填的参考图。[剪辑参数示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/gemini-omni-flash/reference-to-video-developer/README.md)

时长可以用整数选项表示，并按所选分辨率校验。Veo 3.1 Lite 的 720p 可选 4、6 或 8 秒，1080p 要求 8 秒。[分辨率与时长示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/veo3.1-lite/text-to-video/README.md)

Veo 3.1 Lite 的图片来源可接收公开 URL、Base64 数据网址或单行原始 Base64。工作机先检查原始 Base64 的编码、图片格式和大小，再按模型接口提交。[图片来源示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/veo3.1-lite/image-to-video/README.md)

Wan 3.0 Prime 的首尾图片可以使用无透明通道的 PNG。工作机检查上传的原始文件及尺寸，再转换成 Atlas 素材地址。[首尾帧示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-3.0-prime/image-to-video/README.md)

Wan 3.0 Prime 的参考生视频将上传素材和公开地址合并成 `refers` 数组。工作机按图片、视频和音频分别校验数量，检查上传视频与音频各组的累计时长。开启深度思考后，可提交文档地址或网页地址供 Atlas 解析。[多模态参考示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-3.0-prime/reference-to-video/README.md)

Wan 2.7 文生视频可提供 WAV 或 MP3 配乐。工作机检查上传音频的时长与大小，并获取 Atlas 素材地址。用户也可填写公开音频地址，工作机统一通过 `audio` 提交。[配乐示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-2.7/text-to-video/README.md)

Wan 2.7 参考生视频将参考图和视频分别提交到 `images` 与 `videos`。上传和地址合计最多五份，音色参考作为单独的音频字段提交。[引用素材示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-2.7/reference-to-video/README.md)

Wan 2.7 文生图支持预设与自定义尺寸。工作机按总像素和宽高比检查自定义尺寸，并把编辑器中的调色板文本解析为有序的颜色数组。每项含六位色值和两位小数的百分比，合计 100.00%。[调色板示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-2.7/text-to-image/README.md)

Wan 2.6 Flash 图生视频的多镜头模式要求开启提示词扩写。工作机在发送请求前校验两个参数的组合。[镜头模式示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/alibaba/wan-2.6/image-to-video-flash/README.md)

返回音频文件的 Atlas 工作流用 `generateAudio` 提交任务。工作机沿用预测续查和成品回传接口，平台按实际文件内容识别并保存音频。预测响应可在顶层给出 `id` 与 `status`，也可把预测对象放在 `data` 中。[文生语音示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/google/gemini-3.1-flash-tts/README.md)

Atlas 的 3D 工作流可使用 `generateImage` 提交，同时将主成品声明为 `3d`。GLB 使用现有 3D 预览，FBX、OBJ、MTL、STL、USDZ、3MF 和包含模型的 ZIP 作为可下载的原件。工作机保留供应商提供的成品文件名，平台识别文件内容并保存模型随任务返回的贴图和预览。工作流可用布尔字段组装枚举数组，以及声明依赖开关、依赖枚举值和互斥的请求参数。[多图生 3D 示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/meshy-v7/multi-image-to-3d/README.md) · [文生 3D 示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/meshy-v7/text-to-3d/README.md) · [模型归档示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/tencent/hunyuan3d-pro/text-to-3d/README.md)

`integrations/comfyui` 使用轻量 HTTPX/WebSocket 客户端，独立进程与 custom_nodes 入口共用实现，无需在 API 安装 Torch。运行前读取 `/object_info` 检查节点和模型；固定工作流的副本应用参数，原始版本不改动。先连接 WebSocket 再提交 `/prompt`，消息按 prompt ID 隔离。仅 `/history/{id}` 明确成功并包含成品，才进入回传。`executing: node=null` 不作为成功依据。

Qwen Image 2.1 Turbo 文生图的原文与扩写共用同一个 `PrimitiveStringMultiline`。将 `ComfySwitchNode` 的输出经 `PreviewAny` 送入编码器，工作机即可把成功执行中实际采用的文字与成品清单一起回传。任务所有者可在「生成参数」核对原文或扩写分支及实际提示词。

工作机把检查依赖、连接 ComfyUI、重连、等待执行、执行和回传分阶段上报。ComfyUI 接受提交后显示等待执行，收到当前 prompt 的执行事件后显示百分比。

### 断线恢复

工作机将领取凭据、计划的 prompt ID、提交阶段和已完成次数写入仅当前用户可读写的恢复文件 `active.json`。重启后恢复已有队列/历史，不重复提交状态不明的推理。普通传输请求可重试，GPU 任务不会因网络抖动自动重新生成。工作机按对应的 `prompt_id` 移除排队项或请求中断正在执行的任务。断线恢复依赖 ComfyUI 接受客户端指定的 ID，停止正在执行的任务依赖 ComfyUI 支持按该 ID 中断。部分旧版可能中断同一实例上正在执行的其他任务。工作机不清空队列或卸载模型。

工作机同时保存已传入的素材路径、成功历史中的输出描述和平台已确认的成品编号。重启后使用同一份描述和编号回传剩余文件。只有首次达到的步骤和新增的确认会重置重试计时，反复遇到同一个文件的上传故障会达到重试时限。

任务结算时，工作机将未交付的原执行记录到私有状态目录的 `recoveries/`，随后核对原 prompt。补传使用原工作机密钥、租约凭据和原 prompt ID。平台只在失败成品保留期内授权该次执行回传，并在任务锁下检查补跑状态。成功清单按原规则确认。当前接单和补传可分别推进。

### 成品回传与读取

图片/视频通过流式接口上传，限制大小、校验 SHA-256 并读取实际媒体尺寸；上传接口在线程里访问数据库，等待 SQLite 写锁时不阻塞处理其他请求的事件循环，出错时立即回滚释放写锁；图片由 Pillow 验证，视频由受限格式和协议的 ffprobe 验证。文件以随机存储名保存在仓库外，重复上传按任务与客户端成品编号去重。每次执行最多回传 256 份成品（默认值，由 `COMFYSHOP_MAX_EXECUTION_ARTIFACTS` 配置），批次中各次执行分别计数。所属执行完整成功前不能作为成品读取。成功后所有者可通过带权限校验的 FileResponse 查看、Range 播放和下载原文件。访客可访问公开作品选中的成品，关联工作流也须保持公开。

### 结果、作品与工作流封面

执行和作品分别持有可选的图片原件引用。列表将 `coverImage` 用于缩略图，`media` 仍指向实际成品。发布时继承独立图片需要提交预览中的图片摘要，服务端在执行写锁内校验并保存作品自己的引用。封面缩略图通过对应执行或作品的权限读取，来源素材和成品的公开范围由各自的授权控制。作品撤回后访客无法再通过这件作品读取封面，已缓存的缩略图也需重新验证。

结果默认从本次执行选首张图片、首个视频或首份原件。作品从公开的成品中选取默认内容。工作流封面依次选用作者指定的公开作品、作者上传的图片、作者最近公开的作品、官方模型默认图。作者上传新图时会取消作品指定，再次指定和取消作品时保留上传图。前几种封面都缺少时，作者可看到最近成功执行的成品预览。作者上传图单独关联到工作流，模型默认图按 `official_key` 单独登记。两者通过内容去重，缩略图沿用工作流的读取权限。

封面列表在数据库内为每条工作流或任务最多选择一份成品，不向应用层展开作品或成品历史。工作流的公开作品封面、上传图和模型默认图一起批量读取，缺少时再批量读取作者私有封面。任务封面使用一次查询，只取成功执行的成品。公开作品的时间索引支持按顺序取首项。私有封面从该工作流自己的任务出发查找执行，执行状态只作过滤条件。同一时间以 ID 保持稳定选择。

### 缩略图与视频短片

素材和成品提供原件、缩略图地址和长边档位。成品视频还提供静音短片。瀑布流按实际列宽和媒体比例向浏览器提供密度候选。API 使用 160、256、384、512、768、1024、1280 px 档位并以原始长边为上限，不裁切或放大。图片生成 WebP（动图取首帧），视频由 FFmpeg 取首帧 JPEG。结果分组和作品的封面是视频时可以记录取哪一刻的画面（毫秒）：设置时用 ffprobe 核对时间在视频长度之内并随即截出这一帧，超出返回 422，只有视频可以指定。选了画面的封面在 `media` 里给出单独的缩略图地址 `/artifacts/{id}/frames/{毫秒}/thumbnail`，客户端照常追加 `?size=`；这个地址只提供已被某个结果分组或作品选定的时间点，其他时间返回 404。使用作品作为工作流封面时，也会沿用该作品选定的画面。作品指定的封面成品被删除后，改用的成品从首帧开始。首次请求时按需生成。384 和 512 两档缺失时共享一次原件读取与解码或抽帧。原件哈希、实际尺寸、帧时间和处理版本决定派生文件与 ETag。文件原子写入应用卷，S3 模式也保存在私有桶的派生文件前缀中。每次读取缩略图先检查当前素材或成品授权。浏览器可以缓存缩略图，响应为 `private, no-cache` 并带按内容与尺寸档位生成的 ETag，每次使用前回来核对：授权通过且内容未变时返回 304，取消公开或删除后不再返回。缩略图与视频短片各自在独立的线程上限和缓存锁内读取与生成，等待中的请求不占用工作机心跳、领取和回传共用的线程池。其他接口响应不缓存。应用卷和 S3 派生前缀分别按容量和写入时间定期回收。播放中的短片持有独立文件链接，直到响应结束。缓存可随时重建。

视频成品另提供短片地址。按目标长边选取最高 768 px 的档位，首次请求由 FFmpeg 从开头截取最多 10 秒，生成无音轨的 H.264 MP4。短片支持 Range，同一档位原子写入磁盘并复用。每次读取仍检查成品授权。

## 执行、资产与作品

### 执行与种子

`Task → Execution → Artifact` 区分提交批次、实际执行和输出文件。API 在提交时按 `executionCount` 创建执行行，计算并校验每次的整数 `seed`、`noise_seed`。从所选种子起逐次加一，超过字段上限后回到下限。种子字段只校验范围，不校验步长。领取响应的 `executionSeeds` 按执行序号从快照提供精确十进制种子。种子在提交时冻结，领取时只读取快照，快照缺少种子的任务无法领取。工作机任务心跳必须包含执行序号，过期事件不能覆盖后续执行状态。每份资产必须提供执行序号、输出节点、输出槽和顺序，服务端校验后保存非空执行外键；不从文件编号推测归属。

### 成品清单

工作机成功历史按节点、输出槽和文件描述收集资产；相同节点同槽的重复描述去重，不合并不同输出来源。逐个上传后调用执行完成接口，提供有序客户端成品清单。服务器确认全部成员实际存在、顺序与内容一致，再完成该执行。最后一份清单确认时，服务器在同一事务内完成任务并释放工作机。重连后，同一租约可确认成功状态并幂等重放已确认的清单。机器心跳携带设备信息与节点名称，模型选项由节点目录提供。工作机心跳和领取接口校验共享协议库声明的版本，当前为 5。版本不匹配返回 422。取消运行中的任务会向持有效租约的工作机返回 HTTP 409，并通过 `X-ComfyShop-Error-Code: task_cancelled` 指示它停止自己的推理。

### 执行组

批次后续失败、租约过期或密钥撤销只终止未完成执行，已成功组及文件保留。本人结果列表通过 `/executions` 按执行分页。工作流详情的结果、任务摘要和活动轮询都带 `workflow_id` 和 `version_id`。服务端在分页前按所选版本筛选，各版本分别缓存。完成执行数变化时刷新对应范围的结果，保留已加载页数。「我的 → 结果」汇总本站各工作流和版本的结果。组内通过 `/artifacts?execution_id=...` 按输出顺序分页。

结果对比按成品记录的输出节点，从任务冻结图追溯底图。合成沿 destination 输入追踪，裁剪和扩图分别对应负向和正向原图偏移。工作流结果详情与空间结果详情读取同一份任务素材响应，只渲染已授权且几何对应的原图。


### 未完成执行的成品回收

已上传的部分成品从所属执行失败或取消时起默认保留 24 小时，由 `COMFYSHOP_FAILED_ARTIFACT_TTL_SECONDS` 配置。后台按执行状态分批移除过期的成品记录。原件失去最后一个引用后进入回收队列，物理删除失败时记录下次尝试时间，默认间隔 60 秒后重试。文件已不存在时，后台可继续移除成品记录。任务与执行记录保留，同一批次的成功组可继续查看和下载。已成功执行的成品不参与这项回收。

### 作品

`Work` 固定来源执行、版本、作品封面和允许公开的输入。`WorkArtifact` 记录选中的成品及作品内顺序，`WorkAsset` 固定选择公开的参考文件名称和原件引用。使用客户端发布编号与请求哈希避免网络重试重复发布。只有本人成功执行的同组成员可以组成作品，且来源工作流和执行所用版本都须已发布。公开 `/works` 与本人 `/executions` 是独立查询。作品详情与复跑沿用发布时的版本。工作流封面沿用其来源作品的成品授权。

### 软删除

工作流、作品、已结束任务和生成成品的软删除需要所有者会话与有效的 CSRF 值。这四类记录通过 `deleted_at` 标记，由列表和读取权限过滤。记录、公开设置、引用和原文件保留。`DELETE /workflows/{id}` 归档工作流，`POST /works/{id}/delete` 隐藏作品，`DELETE /tasks/{id}` 从历史隐藏已结束任务。执行快照用于查看现有结果及参数，已提交的任务可继续保留来源作品 ID。`DELETE /works/{id}` 继续用于取消公开。

`DELETE /artifacts/{id}` 与 `DELETE /executions/{id}/artifacts` 分别软删除单份成品和整组。删除成品、发布和恢复作品使用同一次执行的写锁。恢复作品前检查全部引用成品，存在已删除成品时返回 409，须先恢复成品。存在作品引用时整次请求返回 409。已删除成品的原文件、缩略图和短片地址均停止提供访问，被删除的成品若是指定的组封面，封面改取剩余可见成品。整组隐藏后，结果列表过滤该组，任务历史仍可显示执行状态。

### 公开参数与重跑

发布范围可选「仅公开成品」「公开参数」和「公开完整输入（含素材）」。网页默认选中并推荐完整输入，确认发布前列出本次执行实际使用的参考文件。完整输入保存节点定义内的标量值和经原任务素材绑定核实的参考文件。API 请求用 `shareAssets: true` 选择完整输入，单独传 `shareParameters: true` 只公开标量。这两个 API 字段默认关闭。历史作品的公开范围取自原发布记录。

作品素材使用作品下的原件和缩略图地址，每次读取都核对作品可见性。撤回、删除作品或归档工作流后停止对访客提供作品素材。本人执行重跑读取原执行的输入，作品重跑读取公开输入。表单按当前工作机字段回填，并保留来源版本。新任务提交时按 `source_work_id` 核对对应字段及素材，复用原件并按接收账号的配额登记素材。素材登记、任务输入冻结和排队在同一事务中完成。已受理的任务凭自身租约取得素材。

历史种子超出当前范围时，表单显示原值，提交需要用户改为有效值。执行与作品的重跑入口都按生成表单的权限检查来源工作流及对应版本。新版本成功发布后可更新发布指针，历史已发布版本与作品保持可读。个人作品和结果在工作流归档后仍可查看，重跑入口返回来源不可用。

## 参数与素材

「本次参数」从当前版本和所选工作机的表单定义读取所有已识别字段，默认展开各分组和只读参数的当前值。搜索按名称、原始字段名和说明匹配，筛选按本次初始值或当前校验结果计算。弹框内临时保存参数和工作机选择，应用后更新本次生成草稿，取消时丢弃暂存变更。作者的版本配置通过「编辑参数」维护。

官方工作流在 `fields` 声明平台字段。在 `parameterLayout` 中用 `fieldId` 引用字段名称，和个人工作流共用分组、顺序、展示名、说明、控件及默认值覆盖规则。`defaultValue` 覆盖字段的 `default`，生成时将表单的有效值冻结到任务快照。JSON 导入时提供初始布局，工作流作者可通过「编辑参数」保存该版本的布局。同步复用版本时，表单和导出 JSON 使用该版本保存的布局。供应商请求字段和模型配置由 `execution.adapter` 对应的适配器解释。 [官方工作流示例](../integrations/official-worker/comfyshop_official_worker/workflows/atlas-cloud/minimax/h3-max/text-to-video/README.md)

作者隐藏的参数默认只读。开启隐藏参数组的「允许编辑」后可编辑本次草稿，组内说明会提示风险和生效范围。关闭开关会锁定输入，已修改时会提示改动已保留。生成区显示已修改的隐藏参数数量，点击可查看改动。修改后可使用「恢复初始值」，再点「应用」恢复本次初始值，重跑的初始值取自历史记录。隐藏选项与当前工作机不兼容时，可通过「待处理」改选可用值。

生成表单从已识别的图节点读取尺寸关系。`ResolutionSelector` 的画幅、像素量和对齐单位用于计算预计宽高，已知的潜空间和模型对齐也纳入计算。`TextEncodeFibo2` 提供自动尺寸和自定义宽高，自动时沿用模型的参考图比例规则。P-H3 若通过同一比例节点和带画幅首行的提示词生成，网页编辑区显示提示词正文，提交时补入所选画幅。未重新编辑画幅和提示词的历史重跑直接使用记录值。

对于使用标准帧数公式的 H3 多参考帧图，表单将参考图和关联时间放在一组。网页和提交接口按图的 24 帧/秒及帧数对齐计算有效范围，提交越界值返回 422。自定义图的公式和连接方式由工作流自行定义。

Pixal3D 四路视图来自同一张图且使用固定裁切时，上传预览按原图像素坐标叠加四个裁切框。所需最小宽高由当前版本的裁切框边界计算。网页标出尺寸不足的字段，提交接口以服务端记录的原图尺寸复核，越界返回 422。

当 `LoadImage` 的图像输出直接连接一个 `ImagePadForOutpaint`，表单提供该素材对应的四个整数边距字段 ID。四边均可见且使用同一整数步长时，网页在素材旁提供扩图画布。画布用 `react-konva` 按需加载，以原图像素计算位置并将四个边距一并写入草稿。提交沿用现有素材和标量参数校验。

当 `InpaintModelConditioning` 或 `VAEEncodeForInpaint` 的参考图和遮罩分别直连 `LoadImage` 和 `LoadImageMask`，且素材一一配对，表单提供对应的遮罩素材和通道字段。当前通道为 `red` 时在参考图旁提供编辑入口。同一个 `LoadImage` 的图片和遮罩输出直连上述重绘节点时，编辑器从原图的反向 alpha 通道读取遮罩。也识别 `VAEEncode → SetLatentNoiseMask` 及中间的 `GrowMask`、`FeatherMask`。未指定新遮罩时沿用原图接线。指定新遮罩时，只在任务的执行图中将该节点的遮罩消费者连接到独立的红通道 PNG，原图文件及图片输出仍按原接线使用。网页在原图像素坐标保存笔画，应用时导出同尺寸的 RGB 遮罩 PNG，白色为重绘区域。上传、权限和执行沿用现有素材流程。缩放和平移作用于画布视图，双指开始缩放时丢弃未完成的笔画。

遮罩编辑器第一次点选物体或人像分区时，从本站加载浏览器 Worker、MediaPipe WASM 和所选模型。点选坐标经当前缩放和平移映射到原图，再归一化传给 MagicTouch。SelfieMulticlass 对同一张参考图一次推理得到分区图。推理预览按原始宽高比例缩小至最长边 1024 像素，结果按原图坐标加入或扣除于现有遮罩，最终导出原图尺寸。Worker 在编辑器关闭或切换模型时释放。前端开发和构建时按固定版本下载并校验模型的 SHA-256，Docker 镜像随站点提供模型和 WASM。[MagicTouch](https://developers.google.com/edge/mediapipe/solutions/vision/interactive_segmenter?tab=Web) · [SelfieMulticlass](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter#multi-class_selfie_segmentation_model)

已识别的画幅和 MoGe 输出选项使用中文标签，提交仍使用工作机目录中的选项值。接到材质烘焙或网格简化节点的参数分别提示贴图尺寸与面数对细节和体积的影响。

### 节点目录与表单

工作机把节点的可编辑基础类型同步到 `machines.catalog`，仅在内容变化时更新。参考文件由用户上传为私有素材。表单哈希根据工作流版本、关联执行节点、有效字段和依赖问题生成。提交时校验哈希，无关节点目录更新和素材上传可以继续使用当前表单。连接型输入保留原始连线，输出节点和密钥字段不开放编辑。

表单接口同时提供版本上的参数布局和当前工作机支持的控件选项。作者的控件和默认值设置保存在 `WorkflowVersion.parameter_layout`。服务端按工作机的类型、范围和选项校验默认值，普通整数还校验步长。字段生效的默认值参与表单哈希并用于补齐提交，重跑从历史记录覆盖表单值。原始 JSON 用于恢复工作流默认值。滑块范围对齐工作机步长，通过缩放后的安全整数传给网页。

生成表单在标签页会话内按账号、工作流版本和重跑来源保留草稿。关闭和重开工作流或返回工作机页面前的表单时会恢复输入。会话切换时清除草稿，「重置参数」恢复当前版本的默认值。「生成」旁显示当前阻塞原因及可用的工作机操作，历史状态在任务记录中查看。

窄屏或较矮的视口将作品区和表单放在同一滚动区，「生成」操作栏保留独立空间。紧凑布局下的工作流标题与关闭按钮独占一行，版本和辅助操作在次行，编辑和删除通过「更多操作」打开。小屏首页的分类和排序同行，触屏的收藏、字段帮助和关闭使用共享触区尺寸。

### 输入校验

表单提交必须包含 `inputValues` 与 `inputSchemaHash`，`executionCount` 表示完整执行次数。服务端检查每个字段的类型、枚举和数值范围，在任务上保存输入值、表单快照和编译后的图。表单读取、重跑和提交时，服务端将带步长的浮点值中极小的表示误差对齐到合法步长值，例如将 `1.0500000000000003` 对齐为 `1.05`。对齐后仍校验范围，原始工作流 JSON 保持原样。超过 JavaScript 安全整数范围的整数以字符串传输，在 Python 端精确恢复。工作机仅使用冻结图与字段定义执行，不回退到工作流默认参数或硬编码节点绑定。表单重跑只接受来源执行或作品。

### 素材上传与配额

`GET /api/v1/assets/usage` 使用与资产库列表相同的空间读取权限。已用容量取写入校验所用的原件用量，剩余为上限减已用且最小为零。文件名和媒体类型筛选仍只作用于列表。

用量读取和容量校验统一调用 `Settings.asset_quota_for` 解析上限。配置按团队固定 ID 覆盖默认值，上传、素材登记、提交和恢复继续在所属空间的写锁内校验。更改上限不会触发素材删除。登记时只校验原件带来的新增占用，复制同一原件的另一种 MIME 记录仍按一份原件计量。

工作流素材字段默认接受 PNG、JPEG、WebP、GIF 图片，MP4、WebM 视频，FLAC 音频和 GLB 模型。Atlas Cloud 已声明 `content_types` 的上传槽位使用其完整格式名单，范围限于平台可识别的上传格式。表单下发的 `acceptedContentTypes` 用于文件选择和入队校验，已发布版本从自身的执行配置解析。裸音频的采样率和声道数由模型约定或工作流参数指定。

上传按实际文件内容识别。HEIC 或 HEIF 原件会收到转换指引，iPhone 将照片转为 JPEG 后可上传。替换失败时，表单标明继续使用的素材。

上传通过带 Cookie/CSRF 的二进制接口完成，图片和视频与输出共用流式接收及媒体验证。`assets` 记录素材所有者和原件哈希，`task_assets` 将其绑定到某个任务的具体节点输入。资产库以外的素材按任务引用回收。未绑定任务的素材默认保留 24 小时，由 `COMFYSHOP_UNUSED_ASSET_TTL_SECONDS` 配置。引用素材的任务及其全部成品都删除后，素材可以释放配额，满同样的保留期后连同引用一起清理。恢复任务或成品时会重新校验所需配额。同一账号上传相同字节且 MIME 相同时复用已有素材并刷新保留期，客户端使用响应里的素材 ID。同一原件可供多份不同 MIME 的素材引用，在账号配额中按一份原件计费。删除未绑定的素材会释放其原件引用。默认素材配额为 10 GiB，由 `COMFYSHOP_ASSET_QUOTA_BYTES` 配置，并发上传在账号锁内校验配额。素材缩略图由所有者读取，原件也可由持有效租约的工作机从关联任务读取。

### 资产库

`assets.saved_at` 记录素材何时存入资产库。有保存时间的素材持续占用所属空间的配额，后台回收跳过这些素材。`GET /api/v1/assets` 按空间列出已保存的素材，按保存时间和 ID 使用游标分页，支持按文件名、媒体类型或工作流字段支持的 MIME 筛选。上传可用 `save_to_library` 在同一事务保存。已有素材可通过 `PUT /assets/{id}/library` 保存。移出通过 `DELETE /assets/{id}/library` 进行，素材若仍有任务引用则清除保存时间。

`PUT /artifacts/{id}/library` 校验成品所属空间、保存权限及成功执行状态，然后将该原件登记为素材。成品存入资产库沿用原件哈希去重以及 `COMFYSHOP_MAX_ASSET_BYTES` 文件上限。工作流选择资产后提交普通素材 ID，工作机凭任务租约下载该素材。

### 素材传入工作机

平台在接收视频时探测时长，随任务素材返回。对于限制视频时长的工作流，官方工作机只在时长已知且符合限制时提交供应商。

工作机下载素材后核验大小及 SHA-256，并上传到 ComfyUI 的 `input/ComfyShop/<task-id>/`。只有任务局部副本替换成此路径，工作流原始版本保持不变。新素材不与上传前的宿主机文件列表比较；ComfyUI 在接收工作流时验证新文件存在。重复传输使用同一路径，不重复提交推理。输入与成品均不由静态目录直接暴露。

## 契约

执行 `pnpm api:generate` 从 FastAPI 导出 `packages/api-client/openapi.json` 并生成 `schema.d.ts`。浏览器请求、实体类型和参数类型均引用该契约。SDK 不保存密码，不包含预置账户。Python 依赖由 uv 锁定；前端由 pnpm 锁定。

官方 API 和工作机的运行测试使用测试内定义的工作流。通过 `pnpm test:python -m 'not official_catalog'` 可单独运行这部分和其他平台测试。默认测试同时读取实际内置目录，验证模型参数、全局唯一导入和五种语言的译文同步。

## 外部 Skill

`integrations/skills/comfyshop/` 保存 Skill 和可独立运行的 Python 客户端。`tooling/build-skill.py` 生成安装入口及 ZIP，复用工作机的 `/downloads` 静态发布路径。安装页 `/skill` 用平台地址生成安装命令。默认安装到 `~/.agents/skills/comfyshop`（Codex）或 `~/.claude/skills/comfyshop`（Claude Code）。

客户端在终端读取账号及密码，通过现有注册或登录接口取得独立 Cookie 会话。会话文件默认位于用户目录的 `~/.comfyshop/sessions/`，按平台地址隔离。密码只用于注册和登录请求，CSRF 值在写操作前从当前会话取得。用户可通过 `logout` 立即撤销 Skill 的会话。Skill 的会话和网页会话各自登录及退出。

业务操作通过客户端定义的动作调用网页使用的 FastAPI 接口，复用账号权限、版本校验、内容可见性与状态约束。操作说明随 ZIP 分发，`operations` 显示通用动作的记录 ID、筛选参数和输出类型。注册登录、工作机密钥、素材传输和批量提交有专用命令。创建或重置工作机时，客户端先以独占模式打开新文件，再发出请求，完整密钥直接写入连接配置。

客户端根据选定版本和工作机读取表单。批量计划保存每套参数及独立幂等键，再逐条调用任务提交接口。一次请求失败会报告已受理的任务和停止项，重试沿用相同键与请求体。工作机使用相同的队列、执行和回传机制。结果链接和下载通过已有媒体鉴权。

官方实践参考：[FastAPI 大型应用](https://fastapi.tiangolo.com/tutorial/bigger-applications/)、[SQLAlchemy Session](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、[OpenAPI TypeScript](https://openapi-ts.dev/introduction)。
