# ComfyShop 工作机

同一份运行代码支持独立入口和 ComfyUI 自启动插件。工作机需要能访问平台和 ComfyUI。可在网页确认接入后取得 API Key，也可预先配置密钥。ComfyUI 地址默认 `http://127.0.0.1:8188`。

## 从网页安装

1. 在工作机上启动 ComfyUI，核对其服务地址，工作机默认使用 `http://127.0.0.1:8188`。使用支持客户端指定 `prompt_id` 和按 ID 中断的版本。使用 Comfy Desktop 安装时选择 Local（本地）。 [ComfyUI 官方安装指南](https://docs.comfy.org/installation/desktop/overview) · [执行与恢复](#执行与恢复)
2. 用工作机能访问的平台地址登录，在“工作机”页下载工作机压缩包。包内 `worker.json` 默认写入下载时的平台地址。设置 `COMFYSHOP_PUBLIC_URL` 可指定包内地址。 [部署配置](../../docs/deployment.md#端口与配置)
3. 将压缩包解压到个人目录，按下表启动。没有密钥时，工作机会申请接入。
   - 本机有桌面环境时自动打开浏览器，登录后确认接入。已有工作机时，新实例请选择“新增工作机”。重装且没有原 `worker.json` 时，停止原进程，等原工作机离线且空闲后，在“接入方式”中选择对应的“重新连接”选项。
   - 远程登录或没有显示器时，窗口里显示二维码、地址和接入代码。用手机扫码，或在任意设备的浏览器打开该地址确认。平台与工作机同机运行且使用 `127.0.0.1` 等回环地址时，终端只显示地址和代码。在其他设备确认时，将浏览器地址的开头换成可访问的平台地址。
   - 也可以在“工作机”页选择“手动添加”，下载含 API Key 的 `worker.json` 覆盖启动文件旁的同名文件。已有密钥时不再申请接入。

   确认后密钥写入 `worker.json`，以后启动直接连接。重新连接会换发密钥，保留原工作机的名称、默认设置和排队任务。同一台设备上的多个实例各用一份配置。配置含 API Key，请保存在仅个人可访问的位置。接入申请 10 分钟内有效，过期后重新启动即可。

4. 保持 ComfyUI 和工作机窗口开启。网页在收到工作机心跳后显示已连接和节点数。连接失败时查看启动窗口的提示并核对配置。重置密钥后结束旧进程，用新配置覆盖 `worker.json` 后重新启动。

| 工作机系统                      | 启动方式                                                 |
| ------------------------------- | -------------------------------------------------------- |
| Windows x64                     | 双击 `start.cmd`                                         |
| macOS（Apple Silicon 或 Intel） | 双击 `start.command`，也可在解压目录运行 `sh ./start.sh` |
| Linux（glibc，x64 或 ARM64）    | 在解压目录运行 `sh ./start.sh`                           |

首次启动需联网。启动器可复用已安装的 uv 和 Python 3.12，缺少时下载所需工具。Linux 自动下载 uv 需要 curl。启动器在解压目录创建 `.venv`，使用从 `uv.lock` 导出的依赖版本和哈希。[uv 安装指南](https://docs.astral.sh/uv/getting-started/installation/)

网页下载包在 `pnpm dev`、`pnpm build` 和 Docker 构建时生成。单独重建下载包时，从仓库根目录运行 `uv run --no-project python tooling/build-worker.py`。

## 独立入口

Python 3.12 或以上版本可以直接运行工作机源码。适用于下载包启动器覆盖范围以外的系统，也可用于手动安装。

1. 登录平台，在“工作机”添加机器并下载配置，也可从“连接设置”单独复制 API Key。每台工作机使用独立密钥。
2. 将下面配置保存为本目录外的 `worker.json`，设为仅当前用户可读（macOS/Linux 为 `chmod 600`）。

```json
{
  "serverUrl": "http://127.0.0.1:8688",
  "comfyUrl": "http://127.0.0.1:8188",
  "apiKey": "替换为工作机的 API Key"
}
```

在仓库的 `integrations/comfyui` 目录安装并启动，使用 Python 3.12 或以上版本。

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
COMFYSHOP_WORKER_CONFIG=/absolute/private/worker.json .venv/bin/python -m comfyshop_worker
```

Windows PowerShell（`python` 需为 3.12 或以上版本）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
$env:COMFYSHOP_WORKER_CONFIG = "C:\private\worker.json"
.\.venv\Scripts\python.exe -m comfyshop_worker
```

独立安装 wheel 后可以直接运行 `comfyshop-worker`，`--once` 表示处理一次领取后退出。密钥保存在仅当前用户可读的配置文件或工作机进程环境中。

### 工作机配置

工作机从自己的进程环境读取配置。进程环境变量优先于 JSON 中的对应字段。[配置加载代码](comfyshop_worker/config.py)

| 环境变量                              | JSON 字段                 | 取值与默认值                                                             |
| ------------------------------------- | ------------------------- | ------------------------------------------------------------------------ |
| `COMFYSHOP_WORKER_CONFIG`             | —                         | 可选的 JSON 文件路径。文件根节点须为对象。                               |
| `COMFYSHOP_SERVER_URL`                | `serverUrl`               | 平台 HTTP(S) 地址，默认 `http://127.0.0.1:8688`。地址只包含连接信息。    |
| `COMFYSHOP_COMFY_URL`                 | `comfyUrl`                | ComfyUI HTTP(S) 地址，默认 `http://127.0.0.1:8188`。地址只包含连接信息。 |
| `COMFYSHOP_API_KEY`                   | `apiKey`                  | 接入后的密钥，首次接入时可省略。                                         |
| `COMFYSHOP_WORKER_STATE_DIR`          | `stateDir`                | 可写的私有状态目录，默认 `~/.local/share/comfyshop/worker/<密钥摘要>/`。 |
| `COMFYSHOP_EXECUTION_TIMEOUT_SECONDS` | `executionTimeoutSeconds` | 有限正数，单位秒，默认 `3600`。JSON 可使用数字或表示数字的字符串。       |

首次接入时，省略环境变量 `COMFYSHOP_API_KEY`，并用 `COMFYSHOP_WORKER_CONFIG` 指定可写的配置文件路径。确认接入后，密钥写入该文件的 `apiKey` 字段。网页启动包的启动脚本已设置配置路径。

连接地址采用无内嵌凭据的 URL。状态目录中的 `active.json` 用于重连后的恢复，记录包含租约凭据。

## ComfyUI 插件入口

将仓库的 `integrations/comfyui` 源码目录复制为 `ComfyUI/custom_nodes/ComfyShop`，使用该 ComfyUI 自己的 Python 环境安装 `requirements.txt`。在启动 ComfyUI 的同一环境设置 `COMFYSHOP_WORKER_CONFIG` 或上述环境变量，再启动 ComfyUI。

插件模式直接使用 ComfyUI 的 Python 环境，不需要创建上面的独立虚拟环境。

插件等待 ComfyUI HTTP 服务就绪后自动连接，不增加工作流节点。既没有 `COMFYSHOP_API_KEY` 也没有 `COMFYSHOP_WORKER_CONFIG` 时不启动；配置文件里还没有密钥时，接入地址和代码写入 ComfyUI 的日志，确认接入后自动开始工作。独立入口与插件入口二选一；同一状态目录的文件锁会防止重复启动。平台每个密钥同时只分配一个任务。

配置示例使用平台与 ComfyUI 的回环地址。跨机器部署时，将 `serverUrl` 改为工作机可访问的平台地址，将 `comfyUrl` 设为工作机可访问的 ComfyUI 地址。使用 Host 白名单时，把平台 IP 或域名加入 `COMFYSHOP_ALLOWED_HOSTS`。

## 执行与恢复

- 仅执行平台分配给当前机器的 API 格式 JSON。编辑器 JSON 可以入库，但需在 ComfyUI 导出 API 格式后运行。
- 工作机同步基础类型的节点输入定义；网页按工作流输入生成表单，未连接的文本、数值、枚举、开关和素材字段可编辑，连接和复杂输入保留原样。节点目录在启动和每次领取后刷新；安装节点或模型后可重启工作机更新网页定义。
- 任务使用冻结的节点输入与编译图，`executionCount` 表示完整执行次数。每次执行直接应用 `executionSeeds` 对应位置提供的种子，十进制字符串在工作机转换为精确整数。
- 图片、视频、FLAC 音频和 GLB 模型素材从平台私有接口下载，工作机校验原始字节后上传到 ComfyUI 的任务专属输入目录。素材类型与大小同时受平台和 ComfyUI 自身限制；不要通过表单复用宿主机上的私人文件路径。
- 平台从所选种子开始逐次加一，超过字段上限后回到下限。工作流自身的批量尺寸保留。一个执行可输出多份图片、视频、FLAC 音频或 GLB 模型，平台分别保存执行与成品。模型采集读取 ComfyUI 保存到输出目录的 GLB。
- 机器心跳与领取必须携带 `protocolVersion: 3`，任务心跳必须带 `executionIndex`。成功历史保留输出节点、输出槽、原文件描述和顺序；同一文件来自不同输出节点时保留各自来源。上传必须通过 `execution_index`、`output_node_id`、`output_slot`、`output_index` 明确绑定到相应执行；文件编号不能替代这些字段。
- 每次执行经 `/worker/tasks/{task}/executions/{index}/start` 绑定 ComfyUI prompt，全部成品上传后在该执行的 `/complete` 提交有序 `clientIds` 清单。平台确认最后一份清单时同时完成任务；任务级 `/complete` 可幂等确认成功。重连优先确认平台状态，必要时使用持久化记录恢复原 prompt 和清单。
- 领取任务后请先让当前任务完成，再升级或切换工作机版本；跨版本更换输出描述格式不应发生在同一个活动日志中。
- 执行前检查节点与枚举模型选项，不安装模型或节点。来自服务器的节点错误、执行错误和中断会回报平台。
- 接收真实 WebSocket 事件并检查历史成功记录，下载原始输出后校验回传。平台 API 使用 `ffprobe` 验证视频和 FLAC 音频。Docker 镜像包含该命令，直接运行 API 时需要在平台环境中安装。
- 状态位于 `~/.local/share/comfyshop/worker/<密钥摘要>/`，可通过 `COMFYSHOP_WORKER_STATE_DIR` 或配置 `stateDir` 更改。里面有租约凭据，应保持私有。
- 断连后重新连接并恢复已有 prompt；提交结果不明时停止并报错。平台拒绝过期租约时，工作机结束该任务的跟踪并清理领取记录，待 ComfyUI 空闲后领取下一条任务。需要重新执行过期任务时，用户在页面再次提交。工作机密钥失效时停止接单。
- 已提交任务连续 15 秒不在 ComfyUI 队列及历史中时报告失败。平台暂时出错（网络中断、5xx 或代理返回的网页）或 ComfyUI 暂时出错时，工作机保留执行记录并以 3 秒起、逐次加倍、最长 60 秒的间隔重试；素材传完、生成进度向前、生成完成或成品回传成功都算有进展，重试从头计时。持续出错、期间没有任何进展超过 15 分钟时把任务记为失败并领取下一条，不重新生成。回报失败期间继续续租，失败原因不会被「连接中断」覆盖。还没领到任务时平台拒绝请求（例如协议版本不一致），同样逐次加长等待并在日志中说明。未预料的错误同样只让当前任务失败，工作机继续运行。每次执行默认限时 3600 秒，通过 `executionTimeoutSeconds` 或 `COMFYSHOP_EXECUTION_TIMEOUT_SECONDS` 配置；开始时间写入日志，重启不会重置限时。超时后，工作机按本次执行的 `prompt_id` 请求停止。
- 断线恢复与停止依赖 ComfyUI 接受客户端指定的 `prompt_id`，并支持按 `prompt_id` 中断。部分旧版会忽略 `prompt_id`，停止时可能中断同一实例上正在执行的其他任务。
- 不清空队列、不卸载模型。用户在平台停止任务时，工作机按该次执行的 `prompt_id` 移除排队项，或向正在执行的 prompt 发出中断请求。租约过期等其他情况只停止跟踪。工作机等 ComfyUI 空闲后领取任务。

## 升级

等任务执行和成品回传完成后，停止 API 与工作机，备份平台数据库和媒体目录，再同步更新平台、网页与工作机。用原系统账号启动新版工作机，并继续使用原配置和私有状态目录。

- 从网页安装时，从更新后的平台下载启动包并解压到新目录。用原来的 `worker.json` 覆盖包内配置，再运行对应的启动文件。如果 `stateDir` 是相对路径，改为指向原状态目录的绝对路径。原配置丢失时，用新包申请接入并在网页选择重新连接原工作机。自定义 ComfyUI 地址等设置需重新填写。
- 独立安装时重新执行 `python -m pip install .`。插件模式更新 `custom_nodes/ComfyShop` 后重启 ComfyUI。

在网页确认原工作机重新上线。使用产出 FLAC 与 GLB 的 API 格式工作流和所需的参考素材，分别在这台工作机上完成一次生成。发布成功的成品，用访客窗口打开作品链接。确认 FLAC 可以播放，GLB 可以旋转预览，并下载原文件核对 SHA-256。带封面图的作品可从成品列表打开 GLB。

工作机协议要求 `protocolVersion: 3`，其他版本的心跳和领取请求返回 422。种子在任务提交时冻结，领取响应按执行序号提供。
