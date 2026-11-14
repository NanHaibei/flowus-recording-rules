---
name: lab-gpu-dispatch
description: "Use the existing lab-platform to dispatch and monitor containerized training/evaluation jobs across the user's lab GPU pool (lab35, lab40, lab51, lab95). 用于 GPU 池任务分发、指定服务器训练、查找空闲显卡、并行评估、日志检查和结果回传。"
---

# 实验室 GPU 池任务分发

复用已部署的 `lab-platform`，将用户当前授权的计算任务发到合适的服务器，核验真实运行并保留可追踪的任务记录。适用于当前 jyz 账户的各个项目，无需依赖原聊天历史。

## 已知入口

- 中心 lab35：`192.168.130.35`；平台目录 `/home/jyz/project/codex_project/infra/lab-platform`。
- CLI：`/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab`。
- API：`http://127.0.0.1:18735/api`；认证文件：平台目录下 `.runtime/token`。在进程中读取，避免打印或复制到任务文件。
- 镜像仓库：`127.0.0.1:18737`；只读监控：`https://nanhaibei.xyz/gpu`。
- 部署说明以平台目录的 `README.md`、`config.local.json`、`labplatform/core.py` 和实时 API 为准；历史驱动信息可能过期。

| 主机 | 地址 | 已知硬件 |
| --- | --- | --- |
| lab35 | 192.168.130.35 | 2 × RTX 4090，平台中心 |
| lab40 | 192.168.130.40 | 8 × RTX 4090 |
| lab51 | 192.168.130.51 | 2 × RTX 5090 |
| lab95 | 192.168.130.95 | 2 × RTX 5090 |

这些是接入信息；可用性、占用、驱动和资源余量必须重新查询。平台提供**显式指定主机和 GPU 的提交**，没有内置自动选机、等待队列、抢占或训练重试。需要自动分发时，在调用侧选择资源并逐个提交。

其他宿主机上的 `127.0.0.1` 不指向 lab35。若当前会话不在中心机器，使用已有 SSH 连接在 lab35 执行 CLI，或通过 SSH 转发连接中心；`code` 和 asset 的 `source` 始终是 **lab35 上的绝对路径**。不要在错误机器上重建平台或改写中心配置。

## 执行流程

### 1. 确认本次任务并查询资源

从当前请求、工作目录和已有配置确定训练入口、数据、输出、指定主机、GPU 数量、资源需求和并行范围。用户已要求运行或分发时，完成必要准备并提交；仅询问无法推断且影响正确性的缺项。查询、解释或创建本 skill 不等于要求启动训练。

同时核对原任务的实验记录器、在线记录配置、日志与检查点保存频率，以及原任务规定的回传主机和绝对路径。原任务已有的记录与回传约定必须随任务分发继承；不能因为改在容器或其他服务器运行就省略。

查询命令：

```bash
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab hosts
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab gpu lab51
```

使用附带的资源查询工具，可同时过滤平台已预留的 GPU：

```bash
python /home/jyz/.codex/skills/lab-gpu-dispatch/scripts/pool_status.py --refresh
# 按实际任务需求增加筛选条件，例如：
python /home/jyz/.codex/skills/lab-gpu-dispatch/scripts/pool_status.py --refresh --min-free-mib 21000 --cpus 8 --memory-gib 32
```

该工具仅查询资源和现有任务，`--refresh` 会刷新监控探针；不会提交、取消或预留 GPU。输出 `candidates` 只表示资源满足筛选条件，**不代表镜像兼容或已取得资源锁**。

仅选择在线、非维护、采样未过期、Docker 可用、`occupancy_known=true`、`busy=false` 且未被任何非终态平台任务预留的 GPU。结合主机 CPU、内存与显存需求判断。不能仅凭利用率低断定空闲。尊重用户指定的主机和卡；用户让平台自行分配时才跨主机选择。无需默认排除 lab35。

### 2. 准备镜像、代码和数据

首次编写任务文件、适配远端环境，或需要继承在线记录与实时回传时，读取 [任务文件、资产和兼容性](references/task-spec.md)。

- 固定并记录本次镜像 digest，核对驱动、PyTorch/CUDA 和 GPU 架构支持。新环境先在同一镜像内做与任务相关的短测，再提交长任务。
- 若已有本地修复或已验证补丁，核对容器实际加载源码的哈希与修复记录；相同包版本号不能证明补丁已进入镜像。复用旧环境快照时先补齐并核验这些修复，再做受控对照。
- 将必要代码导出为不含符号链接和本机环境的普通文件快照；数据、权重用不可变版本 asset 分发。
- 容器 `/workspace` 和 `/inputs/<asset-id>` 只读，输出写入 `/outputs`。容器内 `cuda:0` 是所分配设备的逻辑编号。
- 原任务使用 SwanLab、W&B 等实验记录器时，分发任务必须继承相同记录方式并进行在线数据记录；原任务使用 SwanLab，就必须在分发任务中启用 SwanLab 在线上传。保留原项目/工作区、指标、step 和记录频率，为独立训练建立可关联的 run；未经用户明确变更，不得禁用记录、降级为 offline，或只在训练结束后补传。
- 原任务产生的 `.pt/.pth`、`.yaml/.yml`、训练日志、指标及其他约定输出，必须在训练期间持续增量回传到原任务规定的位置，保留相对目录和命名。提交前确定 `/outputs` 到原任务目录的映射并准备持久同步器；平台终态结果下载不能替代实时回传。具体做法见参考文件的“在线记录与训练期间回传”。
- 5090 的既有验收与实验专用实现见参考文件；不要将某次 SuperMimic 验收扩大成所有程序都兼容。若改动后端版本，记录对实验可比性的影响。

### 3. 提交并确认运行

在用户任务目录保存实际 YAML/JSON 和简短 ledger，记录任务用途、主机、GPU UUID、镜像 digest、asset ID、任务 ID、提交时间和输出位置。需要在线记录或实时回传时，补充记录器、run ID/URL、远端到原任务目录的映射、同步进程/服务、轮询间隔、最后成功同步时间和错误状态；运行状态不要写入 skill 安装目录。

```bash
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab submit /absolute/path/on/lab35/task.yaml --host lab51 --gpus 0
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab status TASK_ID
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab logs TASK_ID
```

可直接使用 `POST /api/tasks` 提交等价 JSON；API 客户端关闭环境代理，使用短超时，不打印 Authorization。提交前重新核对任务和资源；平台仍会在准入及容器启动前检查占用。

`PREPARING` 表示准备中。查询到 `RUNNING` 且日志显示真实计算进展，才报告已运行。需要在线记录时，核验云端 run 已收到真实训练指标；需要实时回传时，核验已经产生的日志/配置确实出现在原任务目录并持续更新，检查点按原保存频率核验。不能仅凭进程存在或打印了 run URL 宣称记录与回传正常。

无需等待整个长训练结束才结束当前聊天，但必须先建立可脱离当前工具调用持续运行的所需同步机制，并交代任务 ID、实际阶段、在线 run 链接、原任务文件位置和同步状态。优先用有限次状态/日志查询；`logs --follow` 为手动交互选项，避免工具无限阻塞。

### 4. 多任务分发和等待

同一 GPU 上逐个执行任务。把独立评估、独立训练、可独立处理的数据批次分到多张空闲卡；有前后依赖的阶段仍按依赖推进。多 GPU 训练必须由程序本身支持，不能靠列出多张 GPU 自动获得分布式训练。

并行数由本次用户范围、程序需求和资源余量决定，同时核对同一主机并发任务的 CPU、内存总需求；历史实验的“最多 3 卡并行”只是该实验设置。记录每个逻辑任务到平台任务 ID 的对应关系，先持久化提交结果再投递下一个。共享 asset 保持不可变；同一主机的资产准备必要时串行化，避免复制和校验并发冲突。

需要持续等待/调度或训练期间实时回传时，复用当前项目已有控制器；否则建立有日志和 ledger 的小型后台控制器，记录轮询间隔、重试预算和停止条件，再结束当前会话。实时回传控制器在本次训练期间持续运行，终态完成最后同步后退出；仅在用户范围需要时建立控制器，不因“池子暂时无空卡”无限轮询或新建无人管理的循环。

- 忙卡、资源暂缺且请求确定未被接受：刷新后尝试下一个允许的候选；等待按既定预算执行。
- 提交响应超时或状态未知：先查 `/api/tasks`、本地 ledger 和已知任务 ID，确认是否已受理，未确认前不重复提交。
- 明确的路径、权限、资产校验、镜像/驱动不兼容和训练错误：查明并修复具体原因，保留失败记录；不归类成忙卡反复重试。
- 训练期间或结束后的回传失败：独立记录同步故障，在预算内重试并报告积压，不重跑训练。只对本次授权任务执行取消；不抢占其他任务。

### 5. 回传结果并报告

```bash
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab results TASK_ID --output /absolute/path/to/results
# 仅在当前任务需要停止时：
/home/jyz/project/codex_project/infra/lab-platform/.venv/bin/lab cancel TASK_ID
```

平台终态为 `SUCCEEDED`、`FAILED`、`CANCELED`；`UNKNOWN` 等其余状态仍保留 GPU 预留。无论成功、失败或取消，都对已产生文件完成最后一次增量回传，检查原任务目录内的日志、配置和已完整保存的模型；在线记录需要正常 flush/finish，并核对末次指标。结果同步状态、在线记录状态与训练状态分开核对；仅下载归档不代表文件已经落到原任务规定的位置。简要报告服务器/GPU、任务 ID、真实阶段、关键结果、run 链接、文件位置及同步状态。

不自动升级驱动、重启 Docker/平台、改防火墙、执行全局 prune 或清理其他人的任务。普通分发通过现有准入与容器隔离完成；平台凭据、SSH 私钥、SwanLab 凭据不得进入代码快照、镜像、YAML 或结果。
