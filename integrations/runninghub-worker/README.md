# RunningHub 工作机

用户在「工作机 → 添加工作机 → 添加 RunningHub 连接」填写名称、站点和 API Key。个人空间和团队空间可分别添加多条连接。团队管理员和所有者负责管理连接，编辑者及以上可使用团队连接导入和生成。每次生成由所选连接对应的 RunningHub 账号承担费用。用户可以直接使用浏览器，GPU 和工作机进程由云端及部署方提供。

在工作机行或「我的 → 工作流」点「从链接或 ID 导入」，填写同站点的工作流链接或数字 ID。作者通过「编辑参数」选择展示位置、顺序、名称、控件和默认值。在生成表单上传参考素材、填写提示词并选择本次工作机。打开已发布版本时，从当前空间的同站点连接中选择。原件保存在当前空间，沿用「我的结果」及作品发布入口。

运行日志通过 Loguru 写入 stderr。设置 `COMFYSHOP_WORKER_LOG_LEVEL=DEBUG` 可查看任务续租、执行序号和阶段，默认级别为 `INFO`。

## 部署

API 和独立执行进程均能访问所选 RunningHub 站点。执行进程还需要访问平台和成品下载域名。为 API 配置 `COMFYSHOP_CONNECTION_ENCRYPTION_KEY`，并为 API 与该工作机配置同一个 `COMFYSHOP_WORKER_SERVICE_TOKENS__RUNNINGHUB`。后者是至少 32 字符的独立随机服务令牌。两项配置示例在项目的 `.env.example` 和 `.env.team.example`。

以下命令分别生成 Fernet 加密密钥和服务令牌。把输出保存到部署环境的私有配置中。备份数据库时一并保管加密密钥，恢复时使用原密钥解密连接。

```sh
uv run --package comfyshop-api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

默认 Compose 部署使用以下命令。团队版在 `docker compose` 后增加 `--env-file <团队配置文件> -f compose.team.yaml`。

```sh
docker compose --profile runninghub up -d --build
```

独立部署时在仓库根目录运行以下命令。配置 `COMFYSHOP_SERVER_URL` 指向平台地址。工作机通过服务令牌领取任务及一次任务租约，API 用这份租约限定可读取的工作机连接。安装后的命令入口为 `comfyshop_runninghub_worker.worker:main`。

```sh
uv run --locked --package comfyshop-runninghub-worker comfyshop-runninghub-worker
```

## 导入与执行

- 导入时读取工作流的 API 格式图，并尝试从同站点的原生 ComfyUI 接口读取节点目录。数值上下限、步长和枚举来自实际控件定义。目录缺失时表单会提示，标量沿用工作流中的类型和值。重新导入可以补充节点定义。 [获取工作流 JSON](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749014) · [原生接口说明](https://www.runninghub.cn/runninghub-api-doc-cn/doc-8287337)
- 执行前核对云端图和导入版本的摘要。工作机上传本次素材，以工作流 ID 和节点覆盖表提交，显式传递冻结后的种子。云端图有变化时重新导入、核对参数并选择新版本运行。 [提交工作流](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749013) · [节点覆盖值](https://www.runninghub.cn/runninghub-api-doc-cn/doc-8287336)
- 工作机按云端任务 ID 续查。云端返回成品后，工作机校验下载域名并将原件回传平台。可以通过 `COMFYSHOP_RUNNINGHUB_OUTPUT_HOSTS` 追加可信成品域名，多个域名用逗号分隔。
- 云端提交前先记录提交意图。提交结果不明确时可在任务详情看到“待核对”，请在对应 RunningHub 账号查看记录。取消任务会记录是否已提交、云端是否受理取消，或是否仍待核对。 [取消任务](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749015)
