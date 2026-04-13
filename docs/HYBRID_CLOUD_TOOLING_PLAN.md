# 混合云/多云平台开源工具方案

> 时间: 2026-04-05  
> 范围: Genion AI Tech 全平台基础设施现代化

---

## 一、现状分析

### 1.1 当前服务清单

| 服务 | 角色 | 端口 | 计算需求 |
|------|------|------|----------|
| **AstraMolecula** | API 网关 + 任务编排 | 8000 | CPU |
| **AstraMolecula-front** | React 前端 (Nginx) | 80 / 3000 | 低 |
| **AutoSARM** (×3 Worker) | SAR 分析并行 Worker | 8030–8032 | CPU 密集 |
| **DockingVina** | 分子对接 (AutoDock Vina + BINANA) | 8002 | CPU |
| **PeptideOpt** | 肽链优化 (OmegaFold + ProteinMPNN + Vina) | 8000+ | GPU 可选 |
| **HighFold-C2C** | 环肽设计 + AlphaFold2 结构预测 | 8003 | GPU 必需 (20–48 GB VRAM) |
| **PostgreSQL** | 共享任务队列 + 用户数据 | 5432 | – |
| **SeaweedFS** | 分布式对象存储 | 9333/8080/8888 | – |

### 1.2 当前架构链路

```
用户浏览器
    ↓
AWS CloudFront (d31nbszkjh476e.cloudfront.net)
    ↓
AWS EC2 Nginx (3.133.131.124:443)  ←─── SSL 终止
    ↓
autossh 反向隧道 (2条: 后端:8000, 前端:3000)
    ↓
本地开发机 (genion-computing)
    ├─ AstraMolecula 后端容器  :8001→:8000
    ├─ AstraMolecula 前端容器  :80
    ├─ AutoSARM Worker ×3      :8030–8032
    ├─ DockingVina             :8002
    ├─ PeptideOpt              :8000+
    ├─ HighFold-C2C            :8003
    ├─ PostgreSQL              :5432
    └─ SeaweedFS 集群           :8888 (Filer)
```

### 1.3 核心痛点

| # | 痛点 | 风险等级 |
|---|------|----------|
| 1 | **autossh 隧道脆弱** — 断连无自动监控/恢复，单点故障 | 🔴 高 |
| 2 | **CloudFront 路由配置错乱** — `/api/*` 绕过前端 Nginx，导致 401 (见 LOGIN_401_BUG_ANALYSIS.md) | 🔴 高 |
| 3 | **部署全靠手动 shell 脚本** — 每个服务独立 `docker-manage.sh`，无统一编排 | 🟠 中 |
| 4 | **无集中日志/监控** — 日志散落容器内、`/logs/`、EC2 多处 | 🟠 中 |
| 5 | **手动 SSL 续期** — Let's Encrypt 90 天，acme.sh 手动操作，到期 2026-04-20 | 🔴 高（紧急）|
| 6 | **PostgreSQL 轮询代替消息队列** — AutoSARM 每 30s 轮询，浪费资源 | 🟡 低 |
| 7 | **GPU 工作负载手动调度** — HighFold-C2C/PeptideOpt 手动指定 | 🟠 中 |
| 8 | **无基础设施即代码 (IaC)** — AWS 资源全靠控制台手动配置，CloudFront 易错配 | 🟠 中 |
| 9 | **无服务发现** — 服务间靠硬编码 IP/端口通信 | 🟡 低 |
| 10 | **AutoSARM 固定 3 个 Worker** — 无动态扩缩容 | 🟡 低 |

---

## 二、推荐开源工具方案

### 第一层：网络基础 — 替换 autossh 隧道

**核心目标**：建立本地机 ↔ EC2 加密 mesh 网络，彻底消除隧道单点故障。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **Headscale** | [juanfont/headscale](https://github.com/juanfont/headscale) | 自托管 Tailscale 控制服务器，WireGuard mesh VPN，零配置 NAT 穿透，单二进制部署 | ★★★ |
| **WireGuard** | [WireGuard/WireGuard](https://github.com/WireGuard/WireGuard) | 内核级 VPN，性能最优，需手动配置 peer | ★★ |
| **Nebula** | [slackhq/nebula](https://github.com/slackhq/nebula) | Slack 开源 overlay 网络，证书认证，适合多节点混合部署 | ★★ |

**推荐 Headscale**：
- 在 EC2 上部署 Headscale 控制节点（单二进制），所有机器安装 Tailscale 客户端即可自动组网
- 每台机器分配固定 VPN 内网 IP（如 `100.64.x.x`），所有服务通过内网 IP 直接通信
- 替代当前 2 条 autossh 隧道，无需在 EC2 上开放额外端口

```bash
# EC2 上部署 Headscale（示例）
docker run -d \
  --name headscale \
  -p 8080:8080 -p 9090:9090 \
  -v ./headscale/config:/etc/headscale \
  headscale/headscale:latest serve

# 本地机加入网络
tailscale up --login-server=https://headscale.genionaitech.com
```

---

### 第二层：容器编排 — 替换分散的 Docker Compose

**核心目标**：统一编排所有服务，支持跨节点调度（本地机 + EC2），GPU 自动调度。

#### 方案 A：K3s（推荐，有 K8s 基础时）

| 属性 | 说明 |
|------|------|
| **GitHub** | [k3s-io/k3s](https://github.com/k3s-io/k3s) |
| **资源** | 单二进制 <512 MB RAM，生产级 Kubernetes |
| **内置组件** | Traefik Ingress、CoreDNS、Flannel CNI、Local Path Provisioner |
| **GPU 支持** | NVIDIA GPU Operator + Device Plugin |
| **优势** | Helm 生态、ArgoCD/Flux GitOps、cert-manager、Prometheus Operator |
| **劣势** | Kubernetes 学习曲线 |

```bash
# EC2 安装 K3s Server 节点
curl -sfL https://get.k3s.io | sh -

# 本地 GPU 机作为 Agent 节点加入
curl -sfL https://get.k3s.io | K3S_URL=https://100.64.x.x:6443 \
  K3S_TOKEN=<node-token> sh -

# NVIDIA GPU Operator（自动配置 GPU 节点）
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install nvidia-gpu-operator nvidia/gpu-operator
```

#### 方案 B：Nomad（推荐，无 K8s 基础时）

| 属性 | 说明 |
|------|------|
| **GitHub** | [hashicorp/nomad](https://github.com/hashicorp/nomad) |
| **资源** | 单二进制，极低资源占用 |
| **特点** | HCL 配置语法，比 K8s YAML 直观；支持 Docker/raw exec/批处理任务 |
| **GPU 支持** | `device "nvidia/gpu"` 原生支持 |
| **配套** | Consul（服务发现）+ Vault（Secrets 管理） |
| **优势** | 学习成本低，配置直观，批处理任务友好 |
| **劣势** | 生态工具少于 K8s |

```hcl
# AutoSARM Worker Nomad Job 示例
job "autosarm" {
  group "workers" {
    count = 3  # 动态扩缩

    task "sarm-worker" {
      driver = "docker"
      config {
        image = "registry/autosarm:latest"
      }
      resources {
        cpu    = 4000
        memory = 8192
      }
    }
  }
}
```

**选择建议**：
- 团队有 K8s 经验或计划使用 Helm/ArgoCD/Prometheus Operator → **K3s**
- 团队更偏运维简单、不想学 K8s YAML → **Nomad**

---

### 第三层：CI/CD 流水线

**核心目标**：自动化镜像构建、测试、推送，替代现有单步 GitHub Actions。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **Gitea + Gitea Actions** | [go-gitea/gitea](https://github.com/go-gitea/gitea) | 自托管 Git，GitHub Actions 兼容语法，可直接复用现有 `.github/workflows/*.yml`，单二进制 Go 应用 | ★★★ |
| **Woodpecker CI** | [woodpecker-ci/woodpecker](https://github.com/woodpecker-ci/woodpecker) | Drone CI 开源分支 (Apache 2.0)，Docker 原生流水线，简单 YAML 配置 | ★★★ |
| **Tekton** | [tektoncd/pipeline](https://github.com/tektoncd/pipeline) | Kubernetes 原生 CI/CD，Pipeline as CRD，配合 K3s + ArgoCD 使用 | ★★ |

**推荐 Gitea Actions**：
- 现有 `cicd/.github/workflows/github-actions-demo.yml` 可直接复用，**无需修改 YAML 语法**
- 自托管后不受 GitHub Actions 免费额度限制
- 可在 EC2 或本地机上部署 Actions Runner

---

### 第四层：GitOps 部署自动化

**核心目标**：Git 仓库 = 部署唯一真相源，所有变更通过 git commit 触发，自动同步。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **ArgoCD** | [argoproj/argo-cd](https://github.com/argoproj/argo-cd) | 声明式 GitOps，自动同步 + 一键回滚 + 多集群支持，Web UI 可视化部署状态 | ★★★ |
| **FluxCD** | [fluxcd/flux2](https://github.com/fluxcd/flux2) | 轻量守护进程模式，Helm/Kustomize 原生支持，适合小团队 | ★★ |

```
Git Push (服务代码/K8s manifests)
    ↓
Gitea Actions: 构建镜像 → 推送 Registry
    ↓
ArgoCD: 检测到镜像版本变更 → 自动滚动部署到 K3s 集群
    ↓
Slack/钉钉告警: 部署成功/失败通知
```

---

### 第五层：可观测性（监控 + 日志）

**核心目标**：集中所有服务的日志和指标，替代分散的 `/logs/` 目录，发现即时告警。

#### PLG Stack（推荐一体化方案）

| 组件 | GitHub | 作用 |
|------|--------|------|
| **Prometheus** | [prometheus/prometheus](https://github.com/prometheus/prometheus) | 指标采集 + AlertManager 告警 |
| **Grafana** | [grafana/grafana](https://github.com/grafana/grafana) | 统一可视化仪表板 |
| **Loki** | [grafana/loki](https://github.com/grafana/loki) | 轻量级日志聚合（替代 ELK/Elasticsearch） |
| **Promtail** | (loki 项目内) | 日志采集 Agent，替代 filebeat |
| **cAdvisor** | [google/cadvisor](https://github.com/google/cadvisor) | 容器级指标（CPU/内存/网络） |
| **Node Exporter** | [prometheus/node_exporter](https://github.com/prometheus/node_exporter) | 主机级指标 |

**关键监控指标**：
- autossh 隧道连通性 → 迁移后替换为 Headscale 节点健康状态
- 各服务 `/health` 端点响应时间
- PostgreSQL 连接池 + 任务队列积压量
- GPU 利用率（HighFold-C2C、PeptideOpt）
- SeaweedFS 存储容量 + 写入延迟

---

### 第六层：Ingress + SSL 自动化

**核心目标**：替代手动配置的 Nginx + 手动续期的 acme.sh，实现 SSL 全自动管理。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **Traefik** (K3s 内置) | [traefik/traefik](https://github.com/traefik/traefik) | 自动 SSL + 动态路由 + 负载均衡，K3s 默认 Ingress Controller | ★★★ |
| **cert-manager** | [cert-manager/cert-manager](https://github.com/cert-manager/cert-manager) | K8s 内自动 Let's Encrypt 证书申请/续期，支持 DNS-01 通配符证书，彻底替代手动 acme.sh | ★★★ |

```yaml
# cert-manager ClusterIssuer 示例（DNS-01 via GoDaddy/Cloudflare）
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: genionaitech-wildcard
spec:
  secretName: genionaitech-tls
  dnsNames:
    - "*.genionaitech.com"
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
```

> ⚠️ 当前 SSL 证书将于 **2026-04-20** 到期，务必在迁移前手动续期一次，或尽快部署 cert-manager 接管。

---

### 第七层：基础设施即代码 (IaC)

**核心目标**：AWS 资源（EC2、CloudFront、DNS、安全组）声明式管理，防止手动配置错误（参见 `LOGIN_401_BUG_ANALYSIS.md`）。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **OpenTofu** | [opentofu/opentofu](https://github.com/opentofu/opentofu) | Terraform 完全开源分支 (MPL 2.0)，管理 AWS 全部资源，版本化基础设施变更 | ★★★ |
| **Pulumi** | [pulumi/pulumi](https://github.com/pulumi/pulumi) | 用 Python/TypeScript 写 IaC，对开发者友好，无需学 HCL | ★★ |

**CloudFront 路由错误的根本解法** — 用 OpenTofu 声明 CloudFront Behaviors：

```hcl
# opentofu/cloudfront.tf
resource "aws_cloudfront_distribution" "platform" {
  # 确保所有请求（含 /api/*）都经过前端 Nginx，由 Nginx 剥离前缀
  default_cache_behavior {
    target_origin_id = "frontend-origin"  # 3.133.131.124:3000
    ...
  }
  # 不再单独配置 /api/* behavior，彻底避免路由绕过
}
```

---

### 第八层：消息队列（替代 PostgreSQL 轮询）

**核心目标**：替换 AutoSARM/DockingVina/PeptideOpt 每 30s 轮询 PostgreSQL 的模式，提高任务响应速度和系统资源利用率。

| 工具 | GitHub | 说明 | 推荐 |
|------|--------|------|------|
| **NATS** + JetStream | [nats-io/nats-server](https://github.com/nats-io/nats-server) | 超轻量消息代理（单二进制 10MB），JetStream 支持持久化，适合微服务通信 | ★★★ |
| **Redis** + Celery | [redis/redis](https://github.com/redis/redis) | Python Celery Worker 天然适配，替换轮询逻辑改造成本最低 | ★★★ |

**Redis + Celery 适配现有服务**（改造成本最低）：

```python
# 现有 AutoSARM task_processor.py（轮询模式）改造示意
from celery import Celery

app = Celery('autosarm', broker='redis://localhost:6379/0')

@app.task
def run_sarm_analysis(task_id: str):
    # 现有逻辑不变，只是触发方式从轮询改为 Celery 推送
    ...
```

---

## 三、推荐整合技术栈

```
┌─────────────────────────────────────────────────────────────┐
│                    基础设施层 (IaC)                          │
│  OpenTofu  →  AWS EC2 / CloudFront / DNS / Security Groups  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    网络层 (Mesh VPN)                         │
│  Headscale  →  本地 GPU 机 ↔ EC2 ↔ 其他节点 加密互通        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   编排层 (Container Orchestration)           │
│  K3s  →  统一集群（EC2 Server + 本地 GPU Agent 节点）        │
│  NVIDIA GPU Operator  →  GPU 自动调度                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   CI/CD + GitOps 层                          │
│  Gitea Actions  →  镜像构建/测试/推送                        │
│  ArgoCD         →  GitOps 自动部署到 K3s                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   网络入口层 (Ingress)                        │
│  Traefik (K3s 内置)  →  路由 + 负载均衡 + SSL 终止           │
│  cert-manager         →  Let's Encrypt 自动证书管理           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   可观测性层                                  │
│  Prometheus + Grafana  →  指标仪表板 + 告警                  │
│  Loki + Promtail       →  集中日志                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   数据层 (保留现有)                           │
│  PostgreSQL   →  任务队列 + 用户数据（保留）                  │
│  SeaweedFS    →  对象存储（保留）                             │
│  NATS/Redis   →  消息队列（可选，替代 PostgreSQL 轮询）       │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、分阶段迁移路径

### Phase 1 — 网络基础（第 1–2 周）🔴 紧急

**目标**：消除 autossh 隧道脆弱性，建立稳定混合云网络基础。

- [ ] ⚠️ **立即手动续期 SSL 证书**（到期时间：2026-04-20）
- [ ] 在 EC2 上部署 Headscale 控制服务器
- [ ] 本地机 + EC2 安装 Tailscale 客户端，加入 mesh 网络
- [ ] 验证所有服务通过 VPN 内网 IP 互通
- [ ] 停用 autossh 隧道，更新 Nginx upstream 为 VPN 内网 IP
- [ ] 同步修复 CloudFront `/api/*` Behavior 配置（参见 `LOGIN_401_BUG_ANALYSIS.md`）

### Phase 2 — 容器编排（第 2–4 周）🟠 高优先级

**目标**：统一所有服务编排，实现跨节点 GPU 自动调度。

- [ ] EC2 安装 K3s server 节点（或 Nomad server）
- [ ] 本地 GPU 机作为 agent 节点加入集群
- [ ] 使用 **Kompose** 工具将 Docker Compose 自动转换为 K8s manifests
  ```bash
  # 自动转换示例
  kompose convert -f docker-compose.yml -o k8s/
  ```
- [ ] 部署 NVIDIA GPU Operator，验证 HighFold-C2C GPU 调度
- [ ] Traefik Ingress 替代 Nginx + CloudFront 复杂路由配置
- [ ] cert-manager 接管 SSL 证书自动续期

### Phase 3 — CI/CD + GitOps（第 3–5 周）🟠 高优先级

**目标**：所有部署通过 git commit 触发，消除手动脚本操作。

- [ ] 部署 Gitea（自托管 Git）
- [ ] 配置 Gitea Actions Runner（复用现有 `.github/workflows/` 文件）
- [ ] 部署 ArgoCD，配置监听各服务 Git 仓库
- [ ] 将所有服务的 K8s manifests 纳入 Git 管理
- [ ] 验证端到端流水线：push → 构建 → ArgoCD 自动部署

### Phase 4 — 可观测性（第 4–6 周）🟡 中优先级

**目标**：集中日志和监控，建立告警体系。

- [ ] 部署 PLG Stack（Prometheus + Loki + Grafana）
- [ ] 配置各服务 `/health` 端点监控 + 告警规则
- [ ] 配置 GPU 利用率仪表板（HighFold-C2C、PeptideOpt）
- [ ] 配置 PostgreSQL 任务队列积压告警
- [ ] 配置 SeaweedFS 存储容量告警

### Phase 5 — IaC + 消息队列（第 5–7 周）🟡 中优先级

**目标**：AWS 资源代码化管理，消除手动配置错误；可选优化任务队列。

- [ ] OpenTofu 声明现有 AWS 资源（EC2、CloudFront、SG、DNS）
- [ ] 将 AWS 基础设施变更纳入 Git 审核流程
- [ ] （可选）Redis + Celery 替代 PostgreSQL 轮询
- [ ] （可选）NATS 替代微服务间直接 HTTP 调用

---

## 五、工具一览索引

| 工具 | 类别 | GitHub | 许可证 | 语言 |
|------|------|--------|--------|------|
| **K3s** | 容器编排 | [k3s-io/k3s](https://github.com/k3s-io/k3s) | Apache 2.0 | Go |
| **Nomad** | 容器编排 | [hashicorp/nomad](https://github.com/hashicorp/nomad) | BUSL 1.1 (免费使用) | Go |
| **Headscale** | Mesh VPN | [juanfont/headscale](https://github.com/juanfont/headscale) | BSD-3 | Go |
| **WireGuard** | VPN | [WireGuard/WireGuard](https://github.com/WireGuard/WireGuard) | GPLv2 | C |
| **Gitea** | Git + CI/CD | [go-gitea/gitea](https://github.com/go-gitea/gitea) | MIT | Go |
| **Woodpecker CI** | CI/CD | [woodpecker-ci/woodpecker](https://github.com/woodpecker-ci/woodpecker) | Apache 2.0 | Go |
| **ArgoCD** | GitOps | [argoproj/argo-cd](https://github.com/argoproj/argo-cd) | Apache 2.0 | Go |
| **FluxCD** | GitOps | [fluxcd/flux2](https://github.com/fluxcd/flux2) | Apache 2.0 | Go |
| **Traefik** | Ingress | [traefik/traefik](https://github.com/traefik/traefik) | MIT | Go |
| **cert-manager** | SSL 管理 | [cert-manager/cert-manager](https://github.com/cert-manager/cert-manager) | Apache 2.0 | Go |
| **Prometheus** | 监控 | [prometheus/prometheus](https://github.com/prometheus/prometheus) | Apache 2.0 | Go |
| **Grafana** | 可视化 | [grafana/grafana](https://github.com/grafana/grafana) | AGPL 3.0 | TypeScript/Go |
| **Loki** | 日志聚合 | [grafana/loki](https://github.com/grafana/loki) | AGPL 3.0 | Go |
| **OpenTofu** | IaC | [opentofu/opentofu](https://github.com/opentofu/opentofu) | MPL 2.0 | Go |
| **NATS** | 消息队列 | [nats-io/nats-server](https://github.com/nats-io/nats-server) | Apache 2.0 | Go |
| **Redis** | 缓存/队列 | [redis/redis](https://github.com/redis/redis) | BSD-3 | C |
| **Kompose** | 迁移工具 | [kubernetes/kompose](https://github.com/kubernetes/kompose) | Apache 2.0 | Go |
| **NVIDIA GPU Operator** | GPU 调度 | [NVIDIA/gpu-operator](https://github.com/NVIDIA/gpu-operator) | Apache 2.0 | Go |

---

## 六、附：相关文档

| 文档 | 说明 |
|------|------|
| [LOGIN_401_BUG_ANALYSIS.md](LOGIN_401_BUG_ANALYSIS.md) | CloudFront 路由配置错误导致 401 的根因分析与修复方案 |
| [NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md) | 当前网络架构详细说明 |
| [AWS_NGINX_CORS_CONFIG.md](AWS_NGINX_CORS_CONFIG.md) | AWS EC2 Nginx CORS 配置说明 |
| [DATABASE_SETUP.md](DATABASE_SETUP.md) | PostgreSQL 数据库初始化说明 |
| [SEAWEEDFS_MIGRATION_COMPLETE.md](SEAWEEDFS_MIGRATION_COMPLETE.md) | SeaweedFS 对象存储迁移完成报告 |
