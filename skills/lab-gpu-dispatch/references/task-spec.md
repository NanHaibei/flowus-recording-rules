# 任务文件、资产和兼容性

在创建任务 YAML、准备资产、适配新镜像、继承在线记录与实时回传，或排查投递失败时读取。中心平台源码位于 `/home/jyz/project/codex_project/infra/lab-platform`；字段定义以 `labplatform/core.py` 的 `TaskSpec` 为准。

## 任务格式

下面是待按本次任务填写的模板；镜像、代码和命令必须替换成实际已验证值，不能直接提交：

```yaml
name: project-training-run
host: lab51
gpus: ["0"]
image: "127.0.0.1:18737/lab/your-image@sha256:REPLACE_WITH_VERIFIED_DIGEST"
code: /home/jyz/project/your-project/job-code
command: ["python", "/workspace/train.py", "--output", "/outputs"]
assets: []
secrets: []
cpus: 4
memory: 16g
shm_size: 4g
workdir: /outputs
diagnostic: false
env: {}
```

- `command` 是参数数组；需要 shell 语义时显式使用容器已有的 shell，按代码进行可靠引用。不要假定容器安装了宿主机命令。
- `code` 为中心 lab35 的普通目录；`code: null` 可用于完全由镜像提供程序的任务。
- `gpus` 接受主机卡序号字符串或 UUID；平台会解析并存储 UUID。CLI `--gpus 0,1` 请求同一主机两张卡。
- 平台禁止在 `env` 中设置 `CUDA_VISIBLE_DEVICES` 或 `NVIDIA_VISIBLE_DEVICES`。单卡程序使用容器内的 `cuda:0`。
- 支持 `cpus`、`memory`、`shm_size` 和 `workdir`；`workdir` 仅接受 `/workspace`、`/outputs`。`memory`、`shm_size` 为正整数加 `m` 或 `g`。请求内存之外至少留出 1 GiB 主机余量。
- 平台没有 `priority`、`retries`、`queue` 等字段，未知字段会拒绝；超时等行为由命令或调用侧控制。
- CPU 诊断需 `diagnostic: true` 和 `gpus: []`；不能把正式 GPU 任务改成 CPU 诊断规避准入。

## 文件和数据分发

```bash
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab asset-add mydata v1 /home/jyz/project/mydata
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab assets
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab cache lab51
```

登记所得 asset ID 通常为 `mydata--v1`。将其放入 `assets` 数组，容器中读取 `/inputs/mydata--v1`。登记后不再修改源内容或清单；新内容登记新版本。对相同内容复用已登记版本，避免每次复制大模型和数据。需要修改资产时先生成独立快照，再登记，不覆盖运行中资产。

`code` 和 asset `source` 必须位于平台 `source_roots`（当前 `/home/jyz/project`）内。查 `GET /api/config` 或中心配置确认。不能把 `/tmp` 临时代码目录直接作为中心代码源；在当前项目的允许目录中导出快照。

代码快照排除 `.venv`、`.git`、`.env`、`.runtime`、`.ssh`、`.swanlab`、`.netrc` 等，拒绝符号链接。只包含运行必需的普通文件；不要复制整个 Python 环境作为代码。容器镜像应自包含环境，不能依赖其他主机恰好拥有相同的宿主路径。

`/workspace`、`/inputs/<asset-id>` 只读，`/outputs` 可写。需要编译、创建缓存或写相对日志的程序使用 `/outputs`，保留显式的 `/workspace/...` 脚本路径。平台同步结果时排除常见运行缓存；需要回传的模型、指标、图片等明确输出到 `/outputs`。结果含符号链接时先导出普通文件。

原任务使用 SwanLab 或用户本次要求 SwanLab 在线记录时，任务必须配置 `secrets: [swanlab]`。凭据由节点私有目录提供，平台挂载到 `/run/secrets/swanlab/.netrc`；任务适配代码按镜像内 SDK 的实际行为设置 `SWANLAB_ROOT` 或等价的凭据读取方式，不能假定平台已经设置该变量。不将 API key 写入环境、镜像、YAML、代码和结果。不擅自拷贝或创建节点凭据。

## 在线记录与训练期间回传

### 继承实验记录器

- 从原任务的启动命令、配置和记录代码确定记录器、在线模式、项目/工作区、run 命名与关联方式、指标、step 和记录频率。原任务使用 SwanLab、W&B 等时，分发后继续使用相同服务在线记录；原任务使用 SwanLab 就必须保留 SwanLab，不能用终端日志、TensorBoard 本地文件或训练后补传代替。
- 核对实际镜像包含所需 SDK、训练入口启用了记录，以及目标节点具备可用凭据和到记录服务的网络连接。当前平台 `secrets` 只接受 `swanlab`；其他记录器使用已获授权且不泄露密钥的既有凭据机制，不能臆造平台字段。无法满足在线记录时，说明具体缺项，不得静默禁用或降级为 offline 后继续长训练。
- 每个独立训练使用可区分、可关联原任务与平台任务 ID 的 run，避免并行任务混写。续训按原任务的 resume 约定处理，不能随意复用其他 run。提交后核验云端实际收到训练指标并保存 run ID/URL；运行期间核对上传进展与错误，结束时正常 flush/finish。原任务没有在线记录要求时，不擅自新增外部记录服务。

### 持续回传原任务输出

1. **记录路径映射。** 在 ledger 写清容器输出子目录、节点实际目录、原任务指定的接收主机/绝对目录及需回传的文件。节点当前把 `/outputs` 挂载到该节点配置的 `<root>/runs/<TASK_ID>/`，其中 `root` 从实时平台配置核对，不硬编码其他节点的路径。若当前聊天、中心 lab35 与原任务目录不在同一主机，必须打通直到原任务目录的整条链路，不能只同步到中心临时目录。多任务遵循原任务的目录划分，防止重名覆盖。
2. **建立独立实时同步。** 当前 `POST /api/tasks/{id}/sync`、`lab results` 仅允许终态任务，不能用于训练期间回传。通过既有 SSH transport，使用 rsync 或已验证的同步器从节点输出目录拉取本次任务文件；同机可直接增量复制。原任务未规定时默认每 10 秒检查一次，小文件持续更新，检查点保存完成后在下一轮开始回传，并记录实际同步延迟。同步原任务产生的 `.pt/.pth`、`.yaml/.yml`、训练 stdout/stderr、指标文件、事件文件及其他约定产物；不能只看 `lab logs` 或只回传最终模型。stdout/stderr 若仅在容器日志中，需在训练入口保存到 `/outputs`，并保留训练程序的退出码。
3. **保证文件可用。** 检查点应先写临时文件再原子重命名，发布完成后同步；若现有程序直接写目标文件，需确认写入完成，并在传输前后核对稳定性，变化时丢弃本次副本并重试。接收端使用临时文件与原子替换，避免半个 `.pt` 被当作可用模型；不使用 `--inplace`，不使用 `--delete` 清理原任务目录。持续增长的日志允许逐轮更新，但不能把文件传输成功等同于检查点已经完整。凭据、缓存和传输临时文件不进入回传结果。
4. **持久运行并核验。** 同步器必须独立于当前工具调用/聊天存活，复用或建立带 PID/服务标识、日志、最后成功时间、错误和重试预算的后台控制器。训练初期验证日志/配置落在原任务目录，并在后续轮询中确认更新；检查点首次保存及后续新增时核对原任务目录内的完整文件。仅创建同步脚本或后台进程不算验证通过。
5. **终态补齐。** 对 `SUCCEEDED`、`FAILED`、`CANCELED` 都回传已产生文件；训练停止并确认文件不再写入后做最后一次同步，核对文件清单和关键检查点的大小/哈希。同步失败只重试传输，耗尽预算时明确报告未同步项并保留远端输出供恢复，不重新训练。`lab results --output` 下载的是 `<TASK_ID>.tar.gz`；若用它做最终归档或补齐，仍需将所需文件安全解包/合并到上述原任务目录并核验，再结束同步器。

## 镜像与 GPU 兼容

### 已验证的 Newton 修复

当前固定的 Newton 1.8.0.dev0 / 71eeba16 环境已验证 PR #4870 的 MPR 修复，安装记录为 `/home/jyz/project/codex_project/experiment/artifacts/newton_nan_20261103/venv-pr4870-install/installed.json`。宿主 `.venv` 的本地补丁不会自动更新以前制作的容器。

对这套版本做 G1 训练或驱动对照时，核对容器实际加载的 `newton/_src/geometry/mpr.py`：已验证修复哈希为 `b91e25cdc3fb082cd46b9923be470a73ad8083f0459ab27c06bfe13b8ba3848d`，旧未修复哈希为 `2f8d138190d028903d2804c6175d98631b7fc4e1bb8b236c5315a33766cd5a21`。在两组环境都包含相同修复、并通过已有 CPU/GPU MPR 回归之前，不把训练 NaN 解释为驱动差异。

升级到其他 Newton 版本时，确认新代码包含等价修复并使用该版本的验证记录，不机械回退到这里的旧版本或把补丁套到未知源码。

同时核对运行时驱动、镜像 `io.lab-platform.min-driver` 标记、PyTorch/CUDA 构建支持的架构，以及任务用到的扩展/JIT 编译器。`torch.cuda.is_available()` 只是初步检查；新环境还需要真实 GPU 内核运算和代表性短任务。

2026-11-04 的 SuperMimic 池化经验：原 CUDA 12.6 环境缺少 5090 所需的原生 Blackwell 支持；专用兼容镜像使用 PyTorch `2.11.0+cu130`，SONIC 保留 `2.7.0+cu128`，并补齐 GCC 和 Python 开发头文件。此镜像最低驱动主版本为 580。以上是**历史验收环境**，不是所有任务的固定版本要求；不复制旧驱动读数作为现状。

既有实验根目录：`/home/jyz/project/codex_project/experiment/artifacts/supermimic_expansion2_20261102`。只在复用该实验环境或诊断同类问题时查看：

- `platform/image.json`、`platform/image_blackwell.json`：镜像 digest、能力、环境版本。
- `platform/qualifications_blackwell/`、`platform/pool-ready-receipt.json`：验收镜像、驱动和工作负载。原记录实际短测覆盖 lab51/GPU0、lab95/GPU0，对同机另一张卡作同型号/驱动系列判断；不要声称每张卡都单独短测过。
- `platform_dispatch.py`：原实验的选卡、ledger、资产与回传参考；`remote_worker.py` 是对应容器任务入口。

这些脚本依赖原实验的目录、数据和轮次策略；不要直接导入到新项目，也不要把“本机优先”“排除 lab35”“最多 3 卡并行”等实验策略变成通用限制。提取必要模式，按当前项目实现。升级后端需在实验记录中说明，保持数据、种子、初始化、训练预算和评估口径可追踪。

## API 和跨宿主机连接

CLI 自动读取平台目录的 `.runtime/token`，也支持 `LAB_URL`、`LAB_TOKEN_FILE`、`LAB_TOKEN`。附带查询脚本还支持 `LAB_PLATFORM_DIR`；这些变量只影响该工具，不修改平台。

自编 API 客户端使用 `Authorization: Bearer ...`，在进程内读 token，关闭环境代理，避免把 token 放进命令行或日志。端点为：

| 操作 | 请求 |
| --- | --- |
| 健康检查 | `GET /api/health` |
| 主机与已登记任务 | `GET /api/hosts`、`GET /api/tasks` |
| 刷新一个主机 | `POST /api/hosts/{host}/refresh` |
| 提交 JSON 任务 | `POST /api/tasks` |
| 任务状态和日志 | `GET /api/tasks/{id}`、`GET /api/tasks/{id}/logs?tail=50` |
| 同步结果 | `POST /api/tasks/{id}/sync` |
| 下载结果归档 | `GET /api/tasks/{id}/results` |
| 取消任务 | `POST /api/tasks/{id}/cancel` |

从其他机器访问中心时，可复用既有 SSH 登录执行中心命令，或运行：

```bash
ssh -N -L 18735:127.0.0.1:18735 jyz@192.168.130.35
```

本地转发端口冲突时换空闲本地端口并设置 `LAB_URL`。通过隧道使用本地 CLI 需要本机已安全配置的 token 文件；否则优先远端执行中心 CLI，避免额外复制凭据。平台已配置专用密钥和 `IdentityAgent=none`；遇到 SSH 问题先检查现有 transport，不依赖桌面 SSH agent，也不要关闭主机密钥校验。

## 失败分类

只有请求明确未受理且原因为 GPU_BUSY、活动任务占用或暂时内存不足，才按资源竞争处理。HTTP 状态码本身不足以判断可重试：409 也可能是固定配置错误。

提交超时后核对已登记任务；`UNKNOWN` 或失联状态继续保留预留，确认远端容器后再处理。终态失败要区分准备失败和运行失败；还没有容器的失败任务可能没有可同步结果。`result_state != SYNCED` 不代表训练失败，单独重试结果同步。

需要短测时通过正常任务准入投递，不绕过平台直接占用其他 GPU。不要因查询失败重启正在服务训练的 Docker、驱动或平台；先查看服务状态和日志，只有当前授权包含运维修改时才执行相应变更。
