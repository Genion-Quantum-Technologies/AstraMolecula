# 任务调度加固计划（AstraMolecula 侧）

> 定位：**AstraMolecula 独占"任务的一切"** —— 调度、领取、重试、超时、取消、进度、失败原因、GPU 排队、配额。
> 对外（aidd-agent 及任何消费方）只暴露一个稳定契约：**下单 → 查状态 → 取结果**。消费方不感知 `tasks` 表、SeaweedFS、GPU 拓扑。
>
> **决策的权威副本在 ADR** —— 职责边界见 [`ADR 0008`](../../../../docs/adr/0008-agent-compute-tools-no-mcp.md)；**调度平面的选型见 [`ADR 0012`](../../../../docs/adr/0012-compute-scheduling-plane-argo.md)**。本文只写**提供侧的实现细节**，不复述决策。

## ✅ 状态：本文大部分内容已成历史（2026-07-14）

**[ADR 0012](../../../../docs/adr/0012-compute-scheduling-plane-argo.md) P0–P3 已全部落地并在生产用真实任务验证。DB-as-queue 不存在了。** 下面的缺陷清单**保留原文**，因为它记录了这些 bug 曾经是什么样、以及为什么"就地硬化"是错的路 —— 但**每一条都已标注结论**。

| | 缺陷 | 结论 |
|---|---|---|
| P0-1 | 失败原因对外不可见 | ✅ **已修**。`GET /tasks/{id}/status` 新增 `info`；operator 直接读失败 pod 的 stdout。实测：`[dock-score] RuntimeError: Command failed: agfr …` |
| P0-2 | `progress` 恒为 0 | ✅ **已修**。新增 `tasks.progress` 列，由 Argo 步骤完成度投影。 |
| P0-3 | `running` 导致消费方提前停轮 | ✅ **已修**。状态由 operator **一处**写入，统一成 `processing`。 |
| P0-4 | 生产跑占位符服务密钥 | ⛔ **仍未修**（与调度器无关）。 |
| P0-5 | autoSARM 在集群里根本不存在 | ⛔ **仍未修**。**镜像至今不存在**，这个 worker 从来没跑过。唯一变化：sarm 任务现在会**可见地失败**（原因写进 `info`），而不是永远静默 `pending`。 |
| P1-1 | 一半 worker 无并发安全领活 | ✅ **整体消失**。轮询/领活代码全部成为死代码（三个 Deployment 已 `replicas: 0`）。Argo 领活，幂等靠确定性 Workflow 名 `t-{task_id}`。 |
| P1-2 | 没有取消端点 | ✅ **已修**。`DELETE /tasks/{id}`。实测：跑到一半的 GPU 作业被终止，**卡当场释放**。 |
| P1-3 | 无超时 / 心跳 / 僵尸回收 | ✅ **已修**。每个 step 都有 `activeDeadlineSeconds`；operator 会把"Workflow 已消失但未达终态"的行标 `failed`。 |
| P1-4 | 无重试 / 退避 | ✅ **已修**。`retryStrategy` + 指数退避。⚠️ 用的是 `OnError`（**pod 级故障**）而**不是** `OnFailure` —— 科学代码非零退出几乎总是输入有问题，重跑只会再撞同一个错。只有 `fetch`/`publish` 用 `OnFailure`。 |
| P1-5 | GPU 争抢 | ✅ **已修**。P0 撤销 time-slicing（整卡）；P1/P2 做到**阶段级 GPU 释放** —— 实测 HighFold 的 `evaluate` 运行期间，`nvidia.com/gpu` 的持有者是**没有人**。 |
| P1-6 | 提交没有幂等键 | ⛔ **仍未修，且容易误判**。幂等性只到**执行层**（同一个 `task_id` 不会跑两遍）；但**HTTP 层重试会产生两个不同的 task_id**，于是两个 workflow、两个 GPU 作业。**确定性 Workflow 名对此完全无效。** |
| P1-7 | 任务依赖（SARM 链）外包给消费方 | ⛔ **仍未修**。后端仍用 409 + 物理复制整个 `SAR_Results` 目录维持这条边；改成 Argo DAG 要动前端依赖的两段式公开 API。 |
| P1-8 | PDB→PDBQT 转换无人认领 | ⛔ **仍未修**（与调度器无关）。docking 链路对 agent 仍然是断的。 |
| P2-* | 契约一致性 / 代码卫生 | 多数仍在。**但 P2-1（状态词表分裂）已消失** —— 只有一个写入方了。 |

**→ 新增的能力（清单里原本没敢要求的）**：真实进度、可读失败原因、取消、阶段级 GPU 释放、每步死线、CPU/RAM 配额，以及 `generate` 搬出 API 进程。

**→ 完整设计**：[`compute_foundry/docs/design.md`](../../compute_foundry/docs/design.md)。**消费侧**：[`aidd-agent-backend/docs/astramolecula-compute-integration.md`](../../../aidd-agent/aidd-agent-backend/docs/astramolecula-compute-integration.md)。

---

## 一、迁移前的现状（**已成历史，2026-07-14 之前**）

> 保留本节是因为它解释了**为什么**要换掉整个平面，而不是逐条打补丁。今天的执行模型见 ADR 0012。

**没有 scheduler 组件。** 一张共享 Postgres `tasks` 表当队列：

| 步骤 | 发生什么 | 证据 |
|---|---|---|
| 1. 下单 | REST router 校验参数 → 往 SeaweedFS 写输入 → `INSERT tasks` 一行 `status='pending'` → 插一行 `*_task_params` → 返回 `task_id` | [`api/routers/docking.py:21-254`](../src/astra_molecula/api/routers/docking.py#L21-L254) |
| 2. **（无动作）** | **后端到此为止 —— 它从不调用任何 worker。** routers 里 `grep httpx\|aiohttp\|requests.post` 零命中 | — |
| 3. 领活 | 四个 headless worker 各自轮询 `tasks` 表，按 `task_type` 过滤 | 见 §2 P1-1 |
| 4. 回写 | worker 直接 UPDATE `tasks.status` | — |
| 5. 取件 | 消费方轮询 `GET /tasks/{id}/status`，终态后取类型专属结果端点 | [`api/routers/tasks.py:741-777`](../src/astra_molecula/api/routers/tasks.py#L741-L777) |

> **今天第 2 步不再是空的**：后端仍然只 INSERT 一行（这是**声明的意图**），但 **compute-foundry operator** 会把它 reconcile 成一个 Argo Workflow。第 3、4 步的四个轮询 worker 已全部下线。
>
> 后端**故意仍然没有任何 Kubernetes 权限** —— 让它直接提交 Workflow 是一次**双写**（INSERT 行 + 建 Workflow），第二步一失败行就永久卡 `pending`，那正是本文要消灭的 bug 类。

`tasks` 表原本是（[`database/init_database_postgres.sql`](../database/init_database_postgres.sql)）：
`id · user_id · task_type · job_dir · status · info · created_at · started_at · finished_at · updated_at`

**当时没有 `priority` / `retry_count` / `worker_id` / `lease` / `heartbeat` / `progress` 列。** 这不是"配置没打开"，是这些能力从未存在。

> **现在多了两列**：`progress SMALLINT` 和 `workflow_name VARCHAR(253)`。后者是一扇**单向门** —— operator 只为 `workflow_name IS NULL` 的 pending 行建 Workflow，且这一列永不清空。没有它的话，Argo 按 TTL 回收掉一个**已完成**的 Workflow 之后，那一行看起来和"从未提交过"一模一样，于是已完成的任务会被永远重跑。
>
> **仍然没有** `priority` / `lease` / `heartbeat` —— 而且**不需要**：租约和心跳是"多个 worker 抢一张表"才需要的东西，现在没有 worker 在抢了。

五个 `task_type`：`docking` · `sarm_analysis`（矩阵与树共用，靠 `sarm_task_params.task_subtype` 区分）· `peptide_optimization` · `highfold_c2c` · `generate`（~~唯一进程内消费，不走队列~~ → **ADR 0012 P3：已搬出 API 进程，现在和其他四种一样走 Argo**）。

---

## 二、缺陷清单

### P0 —— 阻断 agent 集成，必须先修

#### P0-1 失败原因对外不可见（`tasks.info` 是半成品）

当前分支 `feat/tasks-info-column` 的 commit `586b0ab` **只改了 SQL 一个文件**：加了 `info TEXT` 列 + 幂等 `ALTER`。**Python 侧零支持** ——
- `Task` 模型没有 `info` 字段（[`db/models/task.py:19-28`](../src/astra_molecula/db/models/task.py#L19-L28)）；
- `TaskRepository` 的 4 条 SELECT 全部显式列举 9 个字段，**都不含 `info`**（[`db/repositories/task_repository.py:85,105,126,166`](../src/astra_molecula/db/repositories/task_repository.py#L85)）；
- `TaskResponse` 也没有该字段（[`schemas/responses/basic_response.py:54-62`](../src/astra_molecula/schemas/responses/basic_response.py#L54-L62)）。

**后果：HighFold worker 好不容易写进 `tasks.info` 的失败原因，通过任何 API 都读不出来，只能直连 DB 查。** 对 agent 而言这是最大的窟窿 —— 作业失败了，它永远无法告诉用户为什么。

补充：只有 HighFold 会写 `info`；**dockingvina 失败时不写任何原因**（其 `update_task_status` 连 `info` 形参都没有）。

**修复**：`Task` 模型 + 4 条 SELECT + `TaskResponse` 补 `info`；四个 worker 统一在失败路径写入异常摘要。

> 未确证：`init_database_postgres.sql` 启动时不会自动执行（[`app.py:25-47`](../src/astra_molecula/app.py#L25-L47) 的 lifespan 不碰 DB），**生产库是否已 `ALTER` 加上 `info` 列，需要直连 DB 确认**。

#### P0-2 `progress` 恒为 0

DB 无 `progress` 列；[`db/services/task_service.py:35-52`](../src/astra_molecula/db/services/task_service.py#L35-L52) 的 `update_task_status(task_id, status, progress_info)` **收下 `progress_info` 后直接丢弃**（`update_data` 只装 `status` 和时间戳）；而状态端点返回 `getattr(task, 'progress', 0)`（[`api/routers/tasks.py:773`](../src/astra_molecula/api/routers/tasks.py#L773)）—— `Task` 根本没这个属性，**所以永远返回 0**。

`TaskProgressCallback.update_progress()`（[`task_processor.py:31-56`](../src/astra_molecula/task_processor.py#L31-L56)）每次调用都在做无用功。

**修复**：要么落地真进度（加 `progress` 列 + 让 `update_task_status` 真的写 `info`/`progress`），要么**从 API 契约里删掉这个字段**——留着一个恒 0 的字段比没有更糟，消费方会据它做 UX。

#### P0-3 `running` 状态导致消费方提前停止轮询（live bug）

worker 的状态词表是分裂的：

| worker | 领活后写的中间态 |
|---|---|
| autoSARM · peptide_opt | `processing` |
| dockingvina · HighFold_C2C | `running` |

而 [`core/config/api_config.py:30-35`](../src/astra_molecula/core/config/api_config.py#L30-L35) 的 `TASK_STATUS_PRIORITY` **只有 `pending`/`processing`/`finished`/`failed`，没有 `running`**。于是 [`api/routers/tasks.py:763`](../src/astra_molecula/api/routers/tasks.py#L763) 的 `.get(status, 0)` 命中默认值 0 → 状态端点返回 `poll_interval: 0`（语义是"停止轮询"）+ `can_download: false`。

**后果：一个正在跑的 docking / HighFold 任务，会被 API 告知"别再轮了"。** 这是 bug，不是设计选择。

**修复**：`TASK_STATUS_PRIORITY` 补 `running`（一行），并顺手统一状态词表（见 P2-1）。

#### P0-4 生产环境跑的是占位符服务密钥

`kubectl` 实测（2026-07-14，只查 key 名未读取值）：`astramolecula-backend` 的 `envFrom` 挂了 `astramolecula-config` + `astramolecula-secrets`，而 secret 里**只有** `ASTRA_DATABASE_PASSWORD` / `DB_PASSWORD` / `DMAT_POSTGRES_PASSWORD`（各 6 bytes）。

**`SERVICE_API_KEYS` 与 `JWT_SECRET_KEY` 在生产环境的任何地方都没有被注入** → 线上生效的就是 [`core/config/settings.yaml:50-53`](../src/astra_molecula/core/config/settings.yaml#L50-L53) 里的占位符（`third-party-service-key-123` / `another-service-key-456` / `test-api-key-789`），JWT 签名密钥同理。

服务间鉴权机制本身是完备的（`X-API-Key` + `X-External-User-ID` 双头、影子用户全自动创建），**但用一把公开在 git 里的钥匙锁门等于没锁**。agent 集成会把这道门变成真正的攻击面。

**修复**：生成真实密钥 → 写入 `astramolecula-secrets` → 在 deployment 注入 → 确认 `settings.yaml` 的占位符不再生效。

#### P0-5 autoSARM 在集群里根本不存在

`kubectl` 实测：**没有 autoSARM 这个工作负载** —— Deployment / Pod / Service 全部 NotFound。不是 ADR 0008 记录的"3 个副本 ErrImageNeverPull"，是**零副本**。

**后果：任何 `sarm_analysis` 任务提交后永远 pending，无人消费。**

**修复**：二选一 —— 补部署（按 `genion-computing` 上 build → `k3s ctr import` 流程），或明确宣布 SARM 暂不提供、把它从对外契约里摘掉。**不能保持现在这种"API 收单但无人做菜"的状态。**

（同 namespace 下 `dmat-backend` / `dmat-frontend` 也是 `ErrImageNeverPull`，与本议题无关，但同属部署债。）

---

### P1 —— 调度正确性，扩容/故障时出血

#### P1-1 一半的 worker 没有并发安全的领活（隐式依赖 replicas=1）

| worker | 领活方式 | 安全性 |
|---|---|---|
| autoSARM | `SELECT ... FOR UPDATE SKIP LOCKED` | ✅ 真行锁 |
| peptide_opt | `SELECT ... FOR UPDATE SKIP LOCKED` | ✅ 真行锁 |
| **dockingvina** | 裸 `SELECT id,... FROM tasks WHERE status=%s AND task_type=%s` + `fetchall()`，**无 FOR UPDATE、无 SKIP LOCKED、无 LIMIT** | ❌ 非原子"先查后改" |
| **HighFold_C2C** | 同上（同一份代码模式） | ❌ 非原子"先查后改" |

证据：`dockingvina/src/dockingvina/database/db.py:156-161`、`HighFold_C2C/src/highfold_c2c/database/db.py:156-161`。

**这两个 worker 的正确性完全隐式依赖 `replicas=1`**（当前实测确实是 1，所以是**潜伏**问题而非正在出血）。**一旦扩副本，同一个任务会被多个 pod 重复执行** —— 对 GPU 作业意味着显存直接打爆。

> 注：workspace 根 `CLAUDE.md` 里"workers 用 `SELECT … FOR UPDATE SKIP LOCKED`"的说法**只对 2/4 成立**，应一并更正。AstraMolecula 后端仓库本身全仓 0 处 `FOR UPDATE`/`SKIP LOCKED`。

**修复**：把 autoSARM/peptide_opt 的领活 SQL 抄给 dockingvina/HighFold，或抽一个共享的领活函数。在此之前，**这两个 Deployment 的 `replicas` 必须锁死为 1 并加注释说明原因**。

#### P1-2 没有取消端点 —— 跑飞的 GPU 作业停不掉

`AsyncTaskProcessor.cancel_task()` 存在（[`task_processor.py:256-262`](../src/astra_molecula/task_processor.py#L256-L262)），但**没有任何端点调用它**：tasks router 的 21 条路由**全是 GET**，admin router 的 3 条也全是 GET。

**后果**：一个跑飞的 HighFold/peptide GPU 作业，只能靠删 pod 停掉。agent 侧即使实现了用户"取消"意图，也无处投递。

**修复**：`DELETE /tasks/{id}` 或 `POST /tasks/{id}/cancel`，语义为置 `cancelled` 终态 + 通知 worker 中止（worker 需配合检查取消标志）。

#### P1-3 没有超时 / 心跳 / 僵尸任务回收

`tasks` 表无 `heartbeat` / `lease` 列，全仓无任何 reaper。**worker 崩溃（OOM、GPU 掉卡、pod 被驱逐）后，任务永久卡在 `running`/`processing`，没有任何机制把它捞回来。**

这与已知的 HighFold "Stage 2 `No visible GPU devices`" 复发问题叠加会很难受：GPU 掉了 → worker 挂 → 任务永远 running → agent 永远在轮询一个死任务。

**修复**：worker 定期写心跳（或 `updated_at`），加一个 reaper 把超过阈值无心跳的 `running` 任务置 `failed`（并写明 `info='worker_lost'`）。

#### P1-4 没有重试 / 退避 / 死信

`failed` 即终态，无 `retry_count` 列，调度路径 `grep retry` 零命中。一次瞬时故障（SeaweedFS 抖动、GPU 争抢 OOM）就等于任务永久失败，用户必须手工重提。

**修复**：加 `retry_count` + `max_retries`，worker 失败时按类型决定是否重排队。

#### P1-5 GPU 串行化与排队 —— **这是调度职责，不是 agent 的**

> ✅ **本条的"共卡争抢"部分已于 2026-07-14 解决（ADR 0012 P0，已实施并用真实任务验证）**：`nvidia-device-plugin.yaml` 的 `sharing:` 块**整块删除**，5070 现以**整卡 `nvidia.com/gpu: 1`** 通告并由 **`highfold-c2c` 独占**；**`peptide-opt` 已改纯 CPU**（8 个阶段只有 Stage 1 OmegaFold 用 GPU，实测无卡时自动回落 CPU、11-mer 仅 26.5s）。
> 🚨 **绝不要写 `timeSlicing.replicas: 1`** —— device-plugin v0.17.0 拒绝启动（`number of replicas must be >= 2`），节点 GPU allocatable 直接归 0。要整卡必须删掉整个 `sharing:` 块。
> **但调度层面仍未解决**（下文依然成立）：GPU 作业仍跑在长驻 Deployment 里、串行化靠 `replicas: 1` 隐式保证而非调度器、对外无 `queue_position`/`eta`。

5070 节点（`genion-computing`）只有**单张物理 RTX 5070 12GB** —— 这是 AstraMolecula 的**全部 GPU 预算**（2×5090 是 agent 业务线预留，不可占用）。**历史背景**：该卡曾被 device-plugin time-slice 成 `nvidia.com/gpu=2` 两个逻辑 slot，由 HighFold 与 peptide_opt 两个长驻 GPU worker 共用，而 time-slice **只切算力、不隔离显存**（消费级卡无 MIG）—— 这是 HighFold 反复丢 GPU 句柄的使能条件。

ADR 0008 把这个问题的处理压给了 agent 侧（"工具须回传 ETA/队列位置，并避免同时投递多个 GPU 任务"）。**按现在的职责划分，这是错的** —— 消费方不该知道 GPU 拓扑，更不该靠"自觉不并发提交"来维持集群稳定。任何一个消费方（前端、第三方、另一个 agent）不自觉，防线就破了。

**修复方向**：由 AstraMolecula 侧保证 GPU 作业的串行化 —— 最简单的做法是 GPU 类任务共用一个"GPU 槽位"（全局并发上限 1），排队等待，并在状态里暴露 `queue_position` / `eta`。**消费方只管下单，排队是调度器的事。**

> ✅ 已复验（2026-07-14）：GPU 分配实测确认 —— 整卡 `nvidia.com/gpu: 1` 独占给 `highfold-c2c`；ColabFold 日志 `Running on GPU`；AF2 结构 pLDDT 69–73；容器内 `nvidia-smi` 正常。历史现象记录见 workspace memory `highfold-c2c-gpu-loss-recurring`（其根因已随 time-slicing 移除而消除）。

#### P1-6 提交没有幂等键 —— 重试即双跑

全仓 `grep -i idempoten` **只在 `payments.py` 命中**，四个计算提交端点都没有幂等键。

消费方（agent）的 HTTP 客户端自带 retry/backoff。**一次提交请求超时后重试 → 同一个作业被 INSERT 两次 → 同一个作业被跑两遍。**（注：2026-07-14 整卡独占 + `replicas: 1` 之后，形态从"两个 GPU 作业同时打爆 12GB 显存"变成**串行重复执行** —— 浪费成倍 GPU 时间、产出重复结果。缺陷依旧，只是不再 OOM。）

**修复**：四个 `POST` 接受 `Idempotency-Key` 头（或请求体内的 client-side dedup key），同键重复提交返回**同一个 `task_id`** 而非新建。

#### P1-7 任务间依赖（SARM 链）目前外包给了消费方

`POST /sarm/tree` **硬要求 `source_task_id` 指向一个已 `finished` 的 `sarm_analysis` 任务**，否则 409（`api/routers/sarm.py:334-362`）。

于是消费方被迫做两跳编排：analyze → 自己轮询到终态 → tree。**但"任务间依赖（DAG）"就是调度**，不是点菜。让每一个消费方（agent、前端、第三方）各自实现一遍两跳编排并自行判断上游终态，是把 workflow engine 的一半外包出去。

**修复方向**：提供 `depends_on`（提交 tree 时挂在 analyze 上，由调度侧在上游 finished 后自动放行），或提供一个复合端点。**在修好之前，必须在契约里明确写出"这条链由消费方编排"**，而不是让它默默地成为消费方的负担。

#### P1-8 PDB→PDBQT 转换无人认领 ⚠️

`POST /docking` 硬性要求 `receptor_filename` 以 `.pdbqt` 结尾，否则 400（`api/routers/docking.py:49`）；**AstraMolecula 不做任何格式转换**。

但**上游拿到的是 `.pdb`** —— agent 从 searchfoundry / PDB / AlphaFold 取到的靶点结构、用户从 RCSB 下载的文件，全是 `.pdb`。谁来转？

- **不该是 agent**：那等于把 OpenBabel/Meeko 这类化学信息学依赖装进一个业务编排后端，是彻头彻尾的边界泄漏。
- **应该是这里**：`dockingvina` worker 里**本来就装着 OpenBabel + Meeko**。刀在厨房。

**这是"点菜 vs 厨房"这条线上最贵的一个未决问题** —— 它直接决定 docking（唯一被选为"先打通端到端"的链路）能不能真的跑通。

**修复**：`/docking` 接受 `.pdb` 并在服务端转换（或提供独立的 `POST /convert/pdbqt` 端点）。

---

### P2 —— 契约一致性与代码卫生

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| P2-1 | **状态词表分裂**：`running`（docking/highfold）vs `processing`（sarm/peptide）表达同一含义；`queued`/`paused` 是纯死常量，全仓无引用 | [`db/models/task.py:7-16`](../src/astra_molecula/db/models/task.py#L7-L16) | 消费方必须同时认两个词；是 P0-3 的根因 |
| P2-2 | **提交响应形状不一致**：docking/sarm/highfold 回 `201` + `task_id`；**peptide 回 `200` + `id`**（返回 `TaskResponse`，字段名就叫 `id`） | [`api/routers/peptide.py:156-164`](../src/astra_molecula/api/routers/peptide.py#L156-L164) | 任何"读 `resp['task_id']`"的通用 client 在 peptide 上直接崩 |
| P2-3 | **结果端点错误语义两套**：tasks router 把非终态映射为 pending→425 / processing→202 / failed→410 / 其他→409；而 `/sarm` 和 `/highfold` 的结果端点**只实现了 409 分支** | `api/routers/tasks.py:947-1000`；`api/routers/sarm.py:583-594` | 消费方无法写统一的错误处理 |
| P2-4 | **无配额/背压**：`total_compute_units` 只在提交时估算，**从不扣费、从不校验**；`task_cost_service.py` 是 **0 字节空文件** | `wc -c db/services/task_cost_service.py` = 0 | 单用户批量提交可饿死所有人（FIFO 无优先级） |
| P2-5 | **`main_loop()` 是死代码**：文件无 `__main__` 块，全仓无任何地方 import 它 —— `python -m astra_molecula.task_processor` 跑了什么都不会发生。且它一旦被启用会是**灾难**：`fetch_pending()` 不按 `task_type` 过滤，而 `process_task()` 对未知类型 `raise ValueError` → 会把 sarm/highfold/peptide 的任务**全部标记为 failed** | [`task_processor.py:94-103,287-317`](../src/astra_molecula/task_processor.py#L94-L103) | 定时炸弹；且 CLAUDE.md 把它记成了 worker 入口，会误导人 |
| P2-6 | **peptide 的 `job_dir` 存本地 `/tmp` 绝对路径**，而非 SeaweedFS 前缀（其余类型存前缀） | `api/routers/peptide.py:125-128` | 破坏 `job_dir` 的语义一致性，取件端点要特判 |
| P2-7 | `Task` 模型注释 `# 'generate' or 'docking'` 已过时两个功能代（实际 5 种） | [`db/models/task.py:22`](../src/astra_molecula/db/models/task.py#L22) | 误导 |

---

## 三、对外契约的收敛目标

这是 agent（及任何消费方）依赖的**承重墙**。AstraMolecula 应把契约收敛到下面这组不变量，然后**它内部怎么调度，外部一概不需要知道**：

| 不变量 | 现状 | 目标 |
|---|---|---|
| 下单返回 | 形状不一致（P2-2） | **统一 `201` + `{task_id, status, ...}`** |
| 幂等 | 无（P1-6） | `POST` 接受 `Idempotency-Key`，同键返回同一 `task_id` |
| 状态机 | 6 个实际状态 + 2 个死常量，两套词表（P2-1） | **单一词表**：`pending` → `running` → `finished`/`failed`/`cancelled` |
| 进度 `progress` | 恒 0（P0-2） | **建议直接删掉这个字段**。四个 worker 没有任何一个具备真实的分阶段进度语义，硬造一个假百分比比没有更糟。**契约不能带着"要么…要么…"发布，这个决策现在就要做。** |
| `poll_interval` | 对 `running` 错误返回 0（P0-3） | 修好（补 `running`），或与 `progress` 一并删掉，让消费方自定节奏 |
| 失败原因 | 对外不可见（P0-1） | **`GET /tasks/{id}` 必须回 `info` / `failure_reason`** |
| 取消 | 无（P1-2） | `DELETE /tasks/{id}`；**必须明确语义**：返回时 GPU 进程是否已停？是"已取消"还是"取消请求已受理"？一个不保证生效的取消端点对消费方是有害的 API |
| 任务依赖 | SARM 链外包给消费方（P1-7） | `depends_on`，由调度侧放行 |
| 排队可见性 | 无 | GPU 作业回 `queue_position` / `eta`（P1-5） |
| 重试的可见性 | 无重试（P1-4） | 若落地重试，状态会 `running → pending → running`（**非单调**）。**必须在契约里写明**，否则消费方的 poller 会把重试判成异常 |
| 完成通知 | 无（消费方只能轮询） | **可选 P2**：`callback_url`（HMAC 签名 + 幂等）。有了它消费方就能删掉常驻 poller |
| 权威 API 参考 | 手写的 `API_Documentation.md`（已与代码漂移） | **`/openapi.json`**（workspace 文档规范第 7 条：API 参考一律自动生成，不手写） |

### ⚠️ 契约收敛会打断现有的第二个消费方

**agent 不是唯一的消费方 —— `AstraMolecula-front` 是一个活着的生产前端，它今天就在调这些端点：**

- `AstraMolecula-front/src/api/peptideApi.ts:41` → `POST /peptide/optimize`
- `AstraMolecula-front/src/api/sarmApi.ts:385` → `POST /sarm/analyze`
- 以及 `/docking`、`/highfold`、`/tasks/*`

也就是说，**P2-2 那条"把 peptide 的 `200 + id` 统一成 `201 + task_id`"的修复，会直接打断前端**（`peptideApi.ts` 读的就是 `id`）。同理，删掉 `progress`/`poll_interval` 也会打断前端的轮询逻辑。

**因此契约收敛必须带兼容策略，三选一：**

1. **新旧字段并存一个版本**（响应同时给 `id` 和 `task_id`，状态端点同时回 `running` 和 `processing`），前端跟进后再删旧字段 —— **推荐**，风险最低；
2. 给前端排一个同步改动（两个仓同时发版）；
3. 走 `/v2` 新端点，前端留在旧端点上。

**不带兼容策略地执行 §三，就是一张"把现有产品打断"的路线图。**

---

## 四、明确不归 AstraMolecula 的事

- **不感知 agent / LLM / 会话 / 用户对话上下文。** 它只认 `X-External-User-ID` 这个不透明的身份主键。
- **不负责把结果"解读"成自然语言。** 那是 agent 的事。
- **不负责向用户推送通知。** 它只需把状态暴露出来（或将来回调）；投递给谁、怎么呈现，是消费方的事。

---

## 五、决策与 ADR

**职责边界这个决策不住在本文** —— 它的权威副本在 workspace ADR [`0008` 的「修订记录」](../../../../docs/adr/0008-agent-compute-tools-no-mcp.md)，该 ADR 同时记录了它自己被本次复核证伪的五处事实。本文只负责**提供侧的实现细节**。

> 顺带需要更正的还有 **workspace 根 `CLAUDE.md`**：它写"workers 用 `SELECT … FOR UPDATE SKIP LOCKED`"，实际只有 2/4 成立（P1-1）。（ADR 0008 的 worker 表本身没有过度概括，只在 autoSARM 和 peptide_opt 两行标了该锁。）

---

## 六、建议修复顺序

1. **P0-4 密钥** —— 集成的前置条件，也是当前最大的安全债。（顺手一起处理同类债：`.env` 里已提交的 `SQUARE_ACCESS_TOKEN`。）
2. **P0-1 `info` 读路径** + **P0-3 `running`** —— 各是几行的改动，但直接决定 agent 能否告诉用户"失败了/还在跑"。
3. **P0-5 autoSARM** —— 决定 SARM 到底提不提供。
4. **P1-8 PDB→PDBQT** —— docking 是被选为"先打通"的链路，不解决它这条链路根本跑不通。
5. **P1-1 领活 SQL** —— 或至少把 `replicas: 1` 锁死并注释原因。
6. **P1-6 幂等键** —— 在 agent 开始提交之前，否则第一次网络抖动就双跑 GPU。
7. **P1-5 GPU 排队** + **P1-3 僵尸回收** —— 让调度真正配得上"调度"两个字。
8. **P2 契约收敛（带兼容策略）** —— 在 agent 侧写代码之前做，能省掉一整层适配代码。

### 发布路径（别改完就以为完事了）

- **CI 只在 push 到 `main` 时构建镜像**（`.github/workflows/`，`on: push: branches: [main]`）。**当前工作分支是 `feat/tasks-info-column`，推上去不会构建任何镜像。**
- 镜像进集群靠**手工流程**：在 `genion-computing` 上 build → `docker save` → `k3s ctr import` → `rollout restart`（`imagePullPolicy: Never`）。
- 所以上面每一条"一行的改动"，实际成本 = 改一行 + 走一遍手工发布。**排期时按后者算。**

> 仓库 `CLAUDE.md` 记的"CI 只在 `alan-scientific` 触发"**已过期** —— workflow 已移到根 `.github/workflows` 并改为 target `main`。这条也该顺手更正。

### 验收标准（目前两份计划都缺）

本仓配了 pytest。上面每条修复至少要有一个**在修复前必须变红**的守卫，例如：

- P0-3：`GET /tasks/{id}/status` 对一个 `running` 任务返回 `poll_interval > 0`；
- P0-1：`GET /tasks/{id}` 对一个 failed 任务返回非空的 `info`；
- P2-2：`POST /peptide/optimize` 返回 `201` 且响应含 `task_id`（同时兼容期仍含 `id`）。

### 一个必须先澄清的矛盾

P0-1 里标注"生产库是否已 `ALTER` 加上 `info` 列未确证"，而本仓 `CLAUDE.md` 写的是"prod already migrated"。**这两句必有一句错。** 开工第一件事就是直连 prod DB 确认 `tasks.info` 是否存在。
