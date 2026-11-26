# Docker 部署

Web 和 API 使用同一个镜像，在容器内监听 `0.0.0.0:8688`。前端在构建阶段编译，运行时由 FastAPI 提供静态资源，使用同源 Cookie，无需额外 Nginx。

前端构建会为压缩后更小的 JavaScript 文件生成同名 `.js.gz` 文件。自定义部署请保留完整的 `assets/` 目录，FastAPI 会按浏览器声明的编码偏好提供脚本。网页首次展示 GLB 模型时才加载 3D 预览脚本。

## Compose 启动

一套部署以同一套路由提供简体中文、台湾繁体中文、英文、日文和韩文。反向代理将网页路径与 `/api/v1` 转发到同一服务。`COMFYSHOP_PUBLIC_URL` 填写平台的域名根地址，供邮件链接和工作机启动包使用。

基础版和团队版通过 [共用应用配置](../compose.app.yaml) 接收公开地址、Cookie、SMTP、语言及媒体限额等设置。`COMFYSHOP_MAX_ASSET_BYTES` 按字节设置单个输入素材上限，适用于工作流、资产库和封面，默认 256 MiB。`COMFYSHOP_MAX_ARTIFACT_BYTES` 设置平台接受的单个成品上限，默认 1 GiB。ComfyUI 和官方工作机从领取响应读取实际限额，Atlas 内联成品仍受解码上限约束。两项平台设置均可在对应部署的私有环境文件中设置。

`COMFYSHOP_ASSET_QUOTA_BYTES` 是个人空间及未单独配置的团队空间的素材上限，默认 10 GiB。实例维护者可以在私有环境文件用 `COMFYSHOP_TEAM_ASSET_QUOTA_BYTES` 为团队设定独立上限，JSON 对象的键为团队 ID，值为字节数，最小值为 1024。登录后可从 `/api/v1/teams` 读取自己加入的团队及其 ID。下方为两个示例团队分别设置 20 GiB 和 50 GiB。

```dotenv
COMFYSHOP_TEAM_ASSET_QUOTA_BYTES='{"11111111-1111-4111-8111-111111111111":21474836480,"22222222-2222-4222-8222-222222222222":53687091200}'
```

更新额度后，用相同 Compose 环境文件及项目参数执行 `docker compose up -d --no-build --wait app`。资产库显示生效额度。降低额度后保留已存素材，新增占用按调整后的上限校验。

语言优先使用浏览器记住的手动选择，其次为请求的 `Accept-Language`，最后为运行时 `COMFYSHOP_DEFAULT_LANGUAGE`。可选 `zh`、`zh-tw`、`en`、`ja`、`ko`，默认 `zh`。示例 `COMFYSHOP_DEFAULT_LANGUAGE=en` 设英文为回退语言。

`COMFYSHOP_MENU_LANGUAGES` 设置页头语言菜单。示例 `COMFYSHOP_MENU_LANGUAGES=zh,en` 按顺序显示简体中文和英文，省略时显示所有注册语言。配置至少两项时，宽屏显示语言按钮，手机在「显示与语言」菜单中列出语言。配置只影响菜单，所有注册语言仍参与匹配。修改这两项语言设置后，沿用原 Compose 参数执行 `docker compose up -d --no-build --wait app`。

在仓库根目录执行：

```sh
docker compose up -d --build --wait
```

访问 `http://localhost:8688`；其他设备使用服务器实际地址。首次使用全新数据卷时，入口只执行 Alembic 迁移创建表结构，不导入账号、工作流、作品、任务或工作机。用户自行注册账号，再导入工作流、连接工作机。

默认配置如下：

- Compose 项目名为 `comfyshop`，服务名为 `app`。
- 宿主机和容器内端口均为 `8688`，对所有 IPv4 网卡开放。
- `comfyshop-data` 数据卷挂载到 `/data`，保存 SQLite 数据库、原件和派生缓存。新上传的原件写入 `originals/`。
- 容器以 UID/GID `10001` 运行，自动执行迁移，配置 `unless-stopped` 重启策略。
- 健康检查请求 `/api/v1/health`。镜像包含 `ffmpeg` 和 `ffprobe`，用于检查视频采集结果并生成封面与短片。

查看状态、日志或停止服务：

```sh
docker compose ps
docker compose logs -f app
docker compose down
```

正常启动、重启和 `down` 均保留数据卷。使用宿主机目录替代数据卷时，该目录需要允许 UID/GID `10001` 读写。

如果 PostgreSQL 在局域网另一台服务器上，把 `COMFYSHOP_DATABASE_URL` 写入仓库外的私有环境文件，用 `docker compose --env-file "$COMFYSHOP_ENV_FILE" up -d --build --wait` 启动基础版。示例中的 `COMFYSHOP_ENV_FILE` 是调用命令的 Shell 变量，使用前将它设为该私有文件的绝对路径。[环境示例](../.env.example) 中的 `db.lan.example` 需换成应用容器可访问的数据库局域网 IP 或主机名。应用卷保存媒体，业务数据写入指定的 PostgreSQL。已有 SQLite 数据迁入新库的步骤见下方的备份迁移说明。

## ComfyUI 工作机

基础版和团队版共用 [ComfyUI 工作机 Compose 配置](../integrations/comfyui/compose.service.yaml)。容器连接当前 Compose 项目的 API 和已有的 ComfyUI 后端，GPU 计算由该后端执行。

在对应部署的「工作机」页面选择「手动添加工作机」并下载 `worker.json`。将 `comfyUrl` 设为容器能访问的 ComfyUI 地址。把文件放入仓库外的私有目录，并将目录路径填入 `COMFYSHOP_COMFYUI_WORKER_DIR`。默认路径为 `/srv/comfyshop/comfyui-worker`。容器默认以 UID/GID `10001` 运行，可分别通过 `COMFYSHOP_COMFYUI_WORKER_UID` 和 `COMFYSHOP_COMFYUI_WORKER_GID` 设为能读写该目录的用户和组。工作机将接入配置和执行恢复记录保存在这个目录中，每个部署使用独立目录。

```sh
docker compose --env-file "$COMFYSHOP_ENV_FILE" up -d --build --wait comfyui-worker
```

团队版增加 `-f compose.team.yaml`，本地 RustFS 部署同时保留 `--profile rustfs`。如果 `worker.json` 没有密钥，从容器日志读取接入代码，在日志提供的 `/machines/link` 输入代码。接入后在「工作机」页核对心跳、ComfyUI 状态和节点同步时间。

## 官方工作机

基础版和团队版都继承[官方工作机服务配置](../integrations/official-worker/compose.service.yaml)，使用工作机自己的 [Dockerfile](../integrations/official-worker/Dockerfile)。

在私有部署环境文件中设置 `COMFYSHOP_WORKER_SERVICE_TOKENS__OFFICIAL`，供官方工作机和同步容器调用 API。令牌至少 32 字符，可用 `openssl rand -hex 32` 生成。`COMFYSHOP_OFFICIAL_OWNER` 留空时使用 `ComfyShop`。首次创建该账号时设置 `COMFYSHOP_OFFICIAL_OWNER_PASSWORD`（8–128 位），`official-init` 会调用现有注册接口。使用已有账号时，将 `COMFYSHOP_OFFICIAL_OWNER` 设为对应账号的完整用户名，大小写也需一致。此时可以省略密码变量，沿用原登录密码。

参照[工作机环境示例](../integrations/official-worker/.env.example)，在已有的私有部署环境文件里填写 `ATLAS_CLOUD_API_KEY`。如果密钥保存在单独的私有文件，执行下方命令时再传一次 `--env-file /absolute/private/official-worker.env`，路径替换成实际文件。Compose 只向官方工作机注入该密钥。生成费用计入该密钥对应的账号。若 API 使用 `COMFYSHOP_ALLOWED_HOSTS` 限制请求主机名，将内部地址 `app` 加到允许列表。

两种 Compose 版本默认从应用访问 `http://official-worker:8690/quote`，使用官方工作机服务令牌鉴权。报价端口只供内网访问。分开部署时，给官方工作机设置 `COMFYSHOP_OFFICIAL_WORKER_QUOTE_PORT`，给应用设置 `COMFYSHOP_OFFICIAL_QUOTE_URL` 为可达的内网 `/quote` 地址，双方使用同一个官方工作机服务令牌。有多台工作机领取同一适配器的任务时，使用同一个供应商计费账号，以便折扣与报价一致。将应用侧报价地址设为空即可关闭入口。

```sh
docker compose --env-file "$COMFYSHOP_ENV_FILE" up -d --build --wait official-worker
docker compose --env-file "$COMFYSHOP_ENV_FILE" run --rm -T official-init
```

团队版在同一组命令中加 `-f compose.team.yaml` 并使用团队环境文件。`official-worker` 持续领取任务。`official-init` 默认启用 `--draft`，将每个内置条目导入维护账号的「我的工作流」作为一条草稿，同时同步匹配的默认封面。维护账号试跑验收后即可发布。同步结果写入命令输出，`--rm` 会在执行结束后移除初始化容器。

每个官方工作机实例默认最多同时执行 4 次生成。同一任务内的多次生成和其他任务共用这些名额。例如，一个任务正在生成 3 次，另一个任务可以同时生成 1 次。每次生成从准备素材到成品回传占用一个名额，结束后立即释放。成品按原执行序号保存。可在私有部署环境文件中设置 `COMFYSHOP_OFFICIAL_WORKER_MAX_CONCURRENCY` 为正整数，再用上方的 `up` 命令应用配置。直接运行时可用 `comfyshop-official-worker run --max-concurrency 8` 覆盖环境配置，8 为示例值。

内置工作流按 API 供应商和模型保存为 `workflows/<供应商>/<模型路径>/workflow.json`。Atlas Cloud 的模型路径沿用 `execution.config.model`，例如 `workflows/atlas-cloud/bytedance/seedance-2.5-flash/text-to-video/workflow.json`。清单中每个 `key` 对应一份执行定义，`translations` 保存五种语言的名称、简介、标签、选项文案和参数帮助。维护账号可在「我的工作流」上传同一份完整清单。[内置工作流目录](../integrations/official-worker/comfyshop_official_worker/workflows/)

部署时使用同一构建版本的 API 和官方工作机。

`COMFYSHOP_OFFICIAL_OWNER` 配置的维护账号可在「我的 → 工作流 → 导入工作流 → 官方服务清单 JSON → 管理导入权限」按账号名授权或撤销。接收授权的账号可导入清单并更新自己名下的条目。已属于其他作者的全局标识会返回冲突。导入的草稿由导入人试跑、编辑和发布。撤销会阻止后续导入和清单更新，已有工作流继续由原作者管理。

作者重新导入自己的清单时沿用原工作流 ID。只更新译文时复用原执行版本、实际默认值和表单哈希。作者自行编辑的标题、简介和参数说明保留原文。

模型目录可选放置 `cover.webp` 或 `cover.png`，两者同时存在时优先使用 WebP。同步时按 `official_key` 登记默认封面，相同图片复用已登记的媒体。目录中没有封面时也可同步工作流。重复同步保留作者上传的封面和指定的作品。

新增兼容 Atlas 协议的模型可直接上传清单。也可在仓库根目录用 `uv run --project integrations/official-worker --locked comfyshop-official-worker sync /path/to/model.json` 上传自定义文件，使用私有环境变量指定 `COMFYSHOP_SERVER_URL` 与服务凭据。运行中的官方工作机从领取结果读取冻结的模型配置。

## 一起启动三类工作机

准备好 ComfyUI 连接配置、官方令牌及 Atlas 密钥，并按 [RunningHub 部署说明](../integrations/runninghub-worker/README.md#部署) 设置个人连接加密密钥和 RunningHub 服务令牌。基础版可以用一条命令启动平台和三个工作机。

```sh
docker compose --env-file "$COMFYSHOP_ENV_FILE" up -d --build --wait app comfyui-worker official-worker runninghub-worker
```

团队版在同一命令中加 `-f compose.team.yaml` 并使用团队版私有环境文件。三类工作机各有独立的 Compose profile，单独部署其中一类时指定对应服务。首次导入官方工作流草稿另行运行 `official-init`。

### 工作机日志

ComfyUI、官方和 RunningHub 工作机使用 Loguru。容器将日志写入 stderr，每条记录包含带时区的时间、级别、消息和工作机类型 `worker_kind`。领取任务后可按 `task_id` 查找记录，多次执行用 `execution_index` 区分。官方目录同步命令的 stdout 逐行输出结果 JSON。

`COMFYSHOP_WORKER_LOG_LEVEL` 默认 `INFO`，可设为 `DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL`。`INFO` 记录任务领取和执行结果。排查续租、网络重试或逐件回传时，可在私有部署环境文件中设置 `COMFYSHOP_WORKER_LOG_LEVEL=DEBUG`，再应用配置并查看日志。官方工作机的 Atlas 请求还可按 `prediction_id` 跟踪。

```sh
docker compose --env-file "$COMFYSHOP_ENV_FILE" up -d --no-deps comfyui-worker official-worker runninghub-worker
docker compose --env-file "$COMFYSHOP_ENV_FILE" logs -f comfyui-worker official-worker runninghub-worker
```

## 团队版 Compose

[`compose.team.yaml`](../compose.team.yaml) 使用 PostgreSQL 17。默认原文件仍写入应用卷，可选本地 RustFS 或外部 S3 兼容存储。项目和数据卷与基础版各自独立。数据库和 RustFS 端口只在 Compose 网络内可用。团队版需要 Docker Compose v2.20.0 或更新版本。

团队版默认将 Web 和 API 发布到宿主机的 `0.0.0.0:9688`。在宿主机访问 `http://localhost:9688`，其他设备使用服务器的实际 IP 或域名及端口 `9688`。可用 `COMFYSHOP_TEAM_BIND` 和 `COMFYSHOP_TEAM_PORT` 调整宿主机入口。仅通过宿主机上的反向代理提供服务时可设 `COMFYSHOP_TEAM_BIND=127.0.0.1`。

从独立的 [`.env.team.example`](../.env.team.example) 创建环境文件。以下命令中的目录是示例，请指定仓库外的私有目录，并用 `openssl rand -hex 24` 为 `COMFYSHOP_POSTGRES_PASSWORD` 生成 URL 安全的密码。

```sh
TEAM_CONFIG_DIR=/absolute/private/comfyshop-team
TEAM_ENV="$TEAM_CONFIG_DIR/team.env"
install -d -m 700 "$TEAM_CONFIG_DIR"
(umask 077; test -e "$TEAM_ENV" || cp .env.team.example "$TEAM_ENV")
chmod 600 "$TEAM_ENV"

team() {
  docker compose --env-file "$TEAM_ENV" -f compose.team.yaml "$@"
}
```

已有部署若显式设置了 `COMFYSHOP_TEAM_BIND=127.0.0.1`，可改为 `0.0.0.0` 并执行 `team up -d --no-deps --no-build --wait app`，让其他设备可以访问。使用本地 RustFS 时，在 `up` 前保留 `--profile rustfs` 参数。

- **PostgreSQL 和本地存储**。保留 `COMFYSHOP_STORAGE_BACKEND=local`，运行 `team up -d --build --wait`。
- **PostgreSQL 和本地 RustFS**。设置 `COMFYSHOP_STORAGE_BACKEND=s3`、`COMFYSHOP_S3_ENDPOINT_URL=http://rustfs:9000`、`COMFYSHOP_S3_ADDRESSING_STYLE=path`、独立的桶名和访问密钥。运行 `team --profile rustfs up -d --build --wait`，初始化服务核对并按需创建私有桶，成功后 Compose 启动应用。
- **PostgreSQL 和外部 S3**。同样选择 `s3`，将端点、区域、寻址模式、桶名和凭据填入独立环境文件。预先创建私有专用桶，然后运行 `team up -d --build --wait`。初始化服务会核对应用凭据能访问该桶。AWS S3 可省略端点。凭据也可由 SDK 凭据链提供。

S3 账号需要列出桶和读、写、删 `originals/`、`derived/` 下的对象。兼容端点需支持条件 PUT、单段 Range GET 和批量删除对象。原件由 API 鉴权并流式返回，视频拖动使用 `206 Partial Content`。S3 的多段 Range 请求返回完整原件。S3 模式在桶中保存派生文件，应用卷保存本地缓存。应用卷缓存清理后会先尝试读取 S3，缺失时用原件再生成。

基础版也可使用外部 S3。在启动应用之前创建私有专用桶，并在基础版的私有环境文件里使用相同的 `COMFYSHOP_STORAGE_BACKEND` 和 `COMFYSHOP_S3_*` 配置。

开启桶版本控制后，回收原件会写入删除标记，非当前版本继续占用存储。按团队的备份保留期限，为 `originals/` 设置非当前版本到期和过期删除标记清理规则。对 `derived/` 可单独设置较短的非当前版本保留期。应用的派生缓存容量按当前版本计算。

直接运行 API 或使用独立镜像时，可通过 `COMFYSHOP_DATABASE_URL=postgresql+psycopg://…` 接入已有 PostgreSQL。原文件存储的环境变量与团队版相同，数据库与存储可分别选择。

SQLite 和 PostgreSQL 都从同一份 Alembic 初始迁移 `d522fa8dee69` 建库。使用更早预发布修订的部署需要从空库重建。后续数据库变更从此基线追加。

### 从 SQLite 备份迁入团队版

备份须来自使用上述迁移基线的基础版，并在应用停机后制作。归档根目录包含 `comfyshop.db`，有原件时同时包含 `originals/`。先在源实例等待活动任务结束并停止应用。以下示例在仓库外写入备份和校验文件。

```sh
BACKUP_DIR=/absolute/private/comfyshop-backup
install -d -m 700 "$BACKUP_DIR"
umask 077
docker compose stop app
docker compose run --rm --no-deps -T --entrypoint tar app --hard-dereference -C /data -cf - . > "$BACKUP_DIR/data.tar"
(cd "$BACKUP_DIR" && shasum -a 256 data.tar > SHA256SUMS)
```

使用全新的目标数据库和空的原文件存储。以下是 RustFS 示例。若目标使用本地存储或外部 S3，预备好存储后只启动 `db`，其余命令去掉 `--profile rustfs`。

```sh
(cd "$BACKUP_DIR" && shasum -a 256 -c SHA256SUMS)
team --profile rustfs build app
team --profile rustfs up -d --wait db rustfs
team --profile rustfs run --rm -T rustfs-init
team --profile rustfs run --rm --no-deps -T app python -m comfyshop_api.restore_data - < "$BACKUP_DIR/data.tar"
team --profile rustfs up -d --wait
```

导入会先将临时 SQLite 副本升级到目标版本，检查引用、原件大小和 SHA-256，再以事务写入 PostgreSQL，保留账号、工作流版本、任务、执行、作品、工作机记录及媒体 ID。恢复后用原账号重新登录，重新申请重置密码和邮箱确认链接。缩略图、视频封面和短片会按需生成。若最终提交的回执丢失，恢复工具重连 PostgreSQL 核对事务结果。若数据库暂时无法连接，待连接恢复后核对账号和媒体记录。导入中断且目标库为空时，可用同一份备份重试。工具校验目标中已有原件的键、大小和 SHA-256，再补齐缺失文件。

### 团队版备份与容器重建

备份时等待活动任务结束，停止应用后从同一时间点备份数据库和原文件。

```sh
team --profile rustfs stop app
team exec -T db pg_dump -U comfyshop -Fc comfyshop > "$BACKUP_DIR/database.dump"
```

本地存储模式用上节的 `tar` 命令归档应用卷，将命令开头的 `docker compose` 换成 `team`。S3 模式同步备份专用桶，保留对象键及 Content-Type。可使用服务提供的私有桶备份，或者在自管 RustFS 停机后归档其数据卷。恢复团队版时先准备同一份备份的原文件和空 PostgreSQL 数据库，再执行 `team exec -T db pg_restore -U comfyshop -d comfyshop --exit-on-error --single-transaction --no-owner --no-privileges < "$BACKUP_DIR/database.dump"`，最后启动应用。

重建时保留项目名、环境文件和数据卷。以 RustFS 为例运行 `team --profile rustfs up -d --force-recreate --wait`。查看 `team --profile rustfs ps`，请求 `/api/v1/health`，再核对原账号、任务和公开作品能读取。用原账号打开私有素材，确认其他账号和访客无法读取。选择可播放的视频在浏览器拖动进度，网络面板中的原视频 API 应返回 `206` 和 `Content-Range`。撤回公开后再用访客请求原文件，应返回 `404`。

## 端口与配置

平台支持的环境变量、默认值和允许范围见 [`.env.example`](../.env.example)。工作机从自己的启动环境读取设置，取值见 [工作机配置](../integrations/comfyui/README.md#工作机配置)。

`8688` 是默认端口。可用 `COMFYSHOP_PORT` 调整宿主机入口；容器内始终使用 `8688`。例如：

```sh
COMFYSHOP_PORT=9688 docker compose up -d --build --wait
```

API 配置通过 Compose 的 `environment` 注入。将自定义配置保存在仓库外的覆盖文件，例如 `/absolute/private/compose.settings.yaml`：

```yaml
services:
  app:
    environment:
      COMFYSHOP_ALLOWED_HOSTS: '["127.0.0.1","comfyshop.example"]'
```

再使用两个配置文件启动：

```sh
docker compose -f compose.yaml -f /absolute/private/compose.settings.yaml up -d --build --wait
```

将示例域名换成实际域名或 IP，保留 `127.0.0.1` 供健康检查使用。容器默认配置 `COMFYSHOP_DATA_DIR=/data`、`COMFYSHOP_STATIC_DIR=/app/dist`；通过 HTTPS 入口访问时可设置 `COMFYSHOP_COOKIE_SECURE=true`。Compose 的 `--env-file` 用于变量替换，不会自动将所有变量传入应用。

部署在反向代理（例如负责 HTTPS 的 Nginx）之后时：

- 设置 `COMFYSHOP_PUBLIC_URL` 为用户访问的地址，例如 `https://comfyshop.example`。工作机启动包里的 `serverUrl` 和分享预览图使用此地址；未设置时取请求的地址，经代理转发后可能变成 `http://` 或内网地址。
- 设置 uvicorn 读取的 `FORWARDED_ALLOW_IPS` 为代理的地址，即容器看到的代理来源地址，例如 `172.18.0.1`（示例，以实际网络为准）。登录、找回密码和工作机接入申请按来源地址限制频率，不设置时所有访问者共用代理的地址，容易一起被限制。只填写实际的代理地址，不要使用 `*`。代理必须用真实来源覆盖（或追加到末尾）`X-Forwarded-For`，不能原样转发客户端自带的值，例如 Nginx 的 `proxy_set_header X-Forwarded-For $remote_addr;`。
- 代理运行在宿主机时，将 `compose.yaml` 中的原端口映射替换成 `127.0.0.1:${COMFYSHOP_PORT:-8688}:8688`（示例），限制宿主机入口为本机访问。

若用 Caddy 管理 HTTPS，把 Caddy 的 `/data` 挂载到持久卷。重建容器时继续使用同一卷，以保留证书和 ACME 账号。用浏览器或 `openssl s_client` 查看实际证书的到期时间，并用 Caddy 日志检查续期。平台部署与续期分别验证，续期后再次检查公网入口实际送出的证书。

设置 `COMFYSHOP_SMTP_HOST` 及相关变量可发送邮箱确认和密码重置邮件。发送邮件时必须用 `COMFYSHOP_PUBLIC_URL` 配置可信的平台地址。未设置邮件服务时，链接写入受限的服务日志，可用 `docker compose logs app` 查阅。此时若同时省略平台地址，日志会给出站内路径，按实际使用的平台地址打开。

两种 Compose 部署均从私有环境文件读取 [环境变量示例](../.env.example) 中的应用运行参数，包括会话和工作机租约时长、素材和部分成品保留期、执行成品数量上限及邮件链接有效期。修改后重新创建 `app` 容器。自定义 `COMFYSHOP_FFMPEG` 和 `COMFYSHOP_FFPROBE` 时填写容器内的命令名或路径。

`COMFYSHOP_FAILED_ARTIFACT_TTL_SECONDS` 设置部分成品从执行失败或取消到允许回收的保留时长，单位为秒，默认 `86400`，最小 `60`。

工作机独立运行。跨机器部署时，用工作机能访问的平台地址打开网页并下载启动包，或配置 `COMFYSHOP_PUBLIC_URL` 指定包内地址。启动前核对 `worker.json` 中的 `serverUrl`。平台与工作机同机运行时，可用 `http://localhost:8688`。首次启动后在浏览器里确认接入，无桌面环境时可使用终端显示的地址或二维码。也可手动添加工作机并下载包含 API Key 的配置。清空平台后需要重新创建账号、工作机及密钥。GPU 计算与 ComfyUI 依赖由工作机承担。参见 [工作机接入](../integrations/comfyui/README.md)。

### 发布工作机更新

修改 `integrations/comfyui/pyproject.toml` 中的工作机版本，更新 `uv.lock` 后构建。每个正式版本对应一份固定的发布包。平台和工作机使用相同的协议版本，当前为协议 5。签名私钥存放在发布环境，平台数据目录接收发布包、签名清单和公钥。以下为通用示例，输出目录对应平台数据目录下的 `worker-releases`，容器内默认为 `/data/worker-releases`。

```bash
# 第一次发布时生成私钥。以下路径均为示例。
openssl genpkey -algorithm Ed25519 -out /secure/comfyshop-worker-signing.pem
pnpm build
uv run --package comfyshop-worker python tooling/publish-worker-release.py \
  --key /secure/comfyshop-worker-signing.pem /srv/comfyshop-data/worker-releases
```

发布命令先写入签名 ZIP，再原子替换 `release.json`，随后清理平台发布目录中的旧版 ZIP。工作机交付当前任务后获取最新版。如果下载时恰逢发布切换，平台会重新安排这次更新。部署时先升级平台，再用此流程发布和清理旧包。

若构建机和平台分开，先签名到发布环境的暂存目录。将 `release.json` 和摘要命名的 ZIP 一起传到平台侧的暂存目录。运行以下命令，把验证、切换和旧包清理作为一次发布执行。以下路径均为示例。

```bash
uv run --package comfyshop-worker python tooling/publish-worker-release.py \
  --install-from /absolute/staging/worker-release /srv/comfyshop-data/worker-releases
```

首次从可信渠道安装带公钥的工作机启动包。后续在工作机页选择「更新到最新版」。签名保护更新包内容，使用 HTTPS 可保护平台与工作机的连接和控制请求。

## 更新与清空

### 更新

让活动任务完成，停止共用数据库或数据卷的所有应用实例，备份同一时间点的数据库和 `originals/` 下的原件。随后重新构建镜像并启动平台。

```sh
docker compose up -d --build --wait
```

平台和网页使用同一镜像，启动时应用数据库迁移。

从按语言分站的版本升级时，先用独立的 Compose 项目和数据卷恢复数据库与媒体备份并演练。迁移合并公开目录，保留业务记录的 ID、关联和历史快照。旧官方标识重复时只保留一个公开目录入口，原工作流仍可按 ID 打开符合权限的历史链接。迁移完成后按新版路径生成分享和接入链接。如需回退，使用旧镜像和迁移前的同一份数据库与媒体备份。

### 清空平台

下面的示例适用于使用默认 SQLite 和本地媒体卷的基础版。先停止工作机。如果需要保留数据，请先备份。执行命令时使用与启动该实例相同的 Compose 项目名和环境文件。

```sh
docker compose down --volumes
docker compose up -d --build --wait
```

在上述默认配置中，删除数据卷会一起删除账号、工作流、作品、任务、工作机密钥和媒体，重启后从空库建表。团队版使用其部署时的 Compose 文件和配置，包括启用过的 RustFS 配置。外部 PostgreSQL 和外部 S3 中的数据独立于 Compose 卷。这类部署要从空库开始，应指定新的空数据库和独立的媒体存储位置。

上传暂存在 `COMFYSHOP_DATA_DIR` 下的 `staging/`，容器默认使用 `/data/`。跨文件系统复制时，应用会在目标目录下的 `.comfyshop-publish/` 暂存文件，写完后再发布原件或缓存。数据卷须留出并发上传和视频处理所需的空间，并在重建容器时继续挂载。应用用文件锁识别正在使用的暂存目录，后台定期回收失去持有者的文件，并核对未确认的上传。

应用卷的 `thumbnails/`、`video-previews/` 合用一份容量配额，S3 的 `derived/` 使用同样大小的独立配额。派生文件在写入后开始计时，失效后按需重新生成。后台每约 60 秒清掉过期文件，超过容量时从最早写入的文件开始回收。写入高峰时总量可以短暂超过配额。两个 Compose 配置均可通过环境文件调整以下值。

| 环境变量                                 | 默认值                 | 用途                                                                                      |
| ---------------------------------------- | ---------------------- | ----------------------------------------------------------------------------------------- |
| `COMFYSHOP_DERIVATIVE_CACHE_MAX_BYTES`   | `536870912`（512 MiB） | 每层保留的派生文件总字节数。单个文件超过此值时直接返回当次生成结果。设为 `0` 时按需生成。 |
| `COMFYSHOP_DERIVATIVE_CACHE_TTL_SECONDS` | `604800`（7 天）       | 派生文件自写入起的有效期，读取和从 S3 恢复到本地时沿用原有效期。                          |

## 单独使用镜像

```sh
docker build -t comfyshop:local .
docker run -d \
  --name comfyshop \
  --restart unless-stopped \
  -p 8688:8688 \
  --mount type=volume,source=comfyshop-data,target=/data \
  comfyshop:local
```

## 构建与验证

Node.js 阶段按 `pnpm-lock.yaml` 构建前端，并从唯一的 Token 源文件生成邮件调色板。Python 阶段复制该调色板，按 `uv.lock` 安装 API 生产依赖，以非 editable 方式安装应用，并生成工作机和 Skill 的下载文件。运行镜像包含 API 的 Python 环境、迁移、媒体工具与完整 Web 产物，邮件运行不依赖 Node.js 或仓库路径。`COMFYSHOP_STATIC_DIR` 指向自定义 Web 构建目录时，请一并部署其中的 `downloads/` 目录。工作机和 Skill 分别安装到用户自己的设备。

验证安装页 `/skill`、`/downloads/install-comfyshop-skill.py` 和 `/downloads/comfyshop-skill.zip` 均能从部署地址访问。安装命令使用访问页面的来源地址，客户端设备需要能访问该地址。HTTPS 部署使用与网页相同的 Origin 和 Cookie 配置。

`.dockerignore` 排除密钥、数据库、运行状态、宿主机依赖和缓存。新库空数据约束由持久化测试覆盖；容器可在隔离数据卷验证注册登录、媒体上传、健康检查、停止与重建后的数据保留。

```sh
docker compose config --quiet
curl --fail http://localhost:8688/api/v1/health
pnpm check
pnpm test
pnpm build
```

官方参考见 [Compose 服务配置](https://docs.docker.com/reference/compose-file/services/)、[Compose 变量替换](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)、[RustFS Docker 部署](https://docs.rustfs.com/en/installation/container/docker)、[uv Docker 集成](https://docs.astral.sh/uv/guides/integration/docker/)。
