# SeaweedFS 读取慢 / `/structures` 超时 — 集群 DNS (ndots) 根因与修复

> 日期:2026-06-22 · 影响:HighFold 结果类接口(`/results`、`/structures`、`/download`、`/sequences`)经公网返回慢或 Cloudflare 524 · 涉及:`AstraMolecula`(后端代码)+ `infra/k3s-manifests`(DNS 配置)

## 1. 现象

第三方集成方(持 service API-key)经 `https://api.genionaitech.com` 调用 HighFold 结果接口:

- `GET /highfold/{task_id}/results` —— 约 **16–20s** 才返回(客户端超时短则失败)。
- `GET /highfold/{task_id}/structures` —— **>100s**,被 Cloudflare 在 ~100s 砍成 **`HTTP 524`**(524 本身是一个 HTML 超时页,所以也会被误认为"接口返回了 HTML")。

接口与认证都正常(任务存在且 `finished`,凭证拥有该任务,归属校验通过)。问题纯粹是**后端读取耗时**。

## 2. 根因:集群 DNS 解析内部 FQDN 要 ~8 秒

后端容器 `/etc/resolv.conf`:

```
search astramolecula.svc.cluster.local svc.cluster.local cluster.local  public.utexas.edu  tail8bdfa7.ts.net
nameserver 10.43.0.10
options ndots:5
```

- `search` 列表里混入了**两个外部域**:`public.utexas.edu`(疑似校园网 DHCP 泄漏)和 `tail8bdfa7.ts.net`(Tailscale)。它们从**节点的 `/etc/resolv.conf`** 继承进所有 pod。
- 跨命名空间服务用完整 FQDN,例如 `aidd-seaweedfs-filer.aidd-agent.svc.cluster.local`,只有 **4 个点 < `ndots:5`** → 解析器把它当**相对名**,先依次拼 `search` 域去查:
  1. `…svc.cluster.local.astramolecula.svc.cluster.local` → NXDOMAIN
  2. `…svc.cluster.local.svc.cluster.local` → NXDOMAIN
  3. `…svc.cluster.local.cluster.local` → NXDOMAIN
  4. `…svc.cluster.local.public.utexas.edu` → **走外网 DNS,超时**
  5. `…svc.cluster.local.tail8bdfa7.ts.net` → **走外网,超时**
  6. 最后才用绝对名查成功。

外部域那几步累计耗掉 **~8 秒**。

**集群内计时实证**(在 backend pod 内 `python -c socket.gethostbyname`):

| 解析的名字 | 耗时 |
|---|---|
| `aidd-seaweedfs-filer.aidd-agent.svc.cluster.local`(无尾点,代码当前用法) | **8.006s** |
| `aidd-seaweedfs-filer.aidd-agent.svc.cluster.local.`(加尾点 = 绝对名,跳过 search) | **0.000s** |
| `aidd-seaweedfs-filer.aidd-agent`(短名) | 0.001s |

## 3. 为什么只慢存储、不慢 DB

- **存储客户端**:`services/storage/seaweed_storage.py` 原本**每个调用都 `aiohttp.ClientSession()` 新建一个 session** → 每次都重新做 DNS 解析 → 每个 Filer 操作都吃 ~8s。
  - `/results` = `file_exists`(HEAD)+ `download_bytes`(GET)= 2 次 → ~16–20s。
  - `/structures` 还叠了 **N+1**:`list_files_recursive` 只返回路径,丢掉了 filer 已给出的 size,于是对**每个 PDB 再发一次 HEAD**(`get_file_info`)。该任务有 **50 个 PDB** → 1 次列举 + 50 次 HEAD,被 8s 放大到 >100s → 524。
- **DB**:psycopg2 走持久连接池,只在建连时解析一次 DNS,之后复用 → 一直很快(`/params` 预热后 ~0.07s)。**同一个 DNS bug,被连接池掩盖了**,这也是为什么排查时容易误判成"只是存储/SeaweedFS 的问题"。

## 4. 修复

### ① 热修(零改代码、零重建):给 backend 加 `ndots:2`

`infra/k3s-manifests/apps/astramolecula/astramolecula-backend.yaml`,在 `spec.template.spec` 下加:

```yaml
      dnsConfig:
        options:
          - name: ndots
            value: "2"
```

FQDN(≥2 个点)直接按**绝对名**解析,跳过 search 展开 → 8s 变 0s。`kubectl apply` + `rollout restart` 即生效。

### ② 代码硬化(防御纵深):复用 session + 去 N+1 + 超时

提交 `2b3b470`(分支 `alan-scientific2`,镜像 `astramolecula:latest` config `sha256:09be665e`):

- `seaweed_storage.py`:复用**单个** `aiohttp.ClientSession`,底层 `TCPConnector(use_dns_cache=True, ttl_dns_cache=300)` → filer 主机名只解析一次;并加 `ClientTimeout(total=120, connect=10, …)`,让连接卡住时**快速失败**而非 aiohttp 默认的 300s 挂死。11 处 `ClientSession()` 通过一个不关闭的共享上下文管理器 `_session_cm()` 统一替换。
- 新增 `list_entries_recursive()`:从 filer 列举结果直接带出每个文件的 size(`FileSize`,无则用 chunks 求和),`highfold_results.list_structures` 改用它,**不再对每个 PDB 发 HEAD**(消除 N+1)。响应结构(含 `size`)不变。

## 5. 修复前后实测(公网,客户真实凭证)

| 端点 | 最初 | ① ndots 热修后 | ② + 代码硬化后 |
|---|---|---|---|
| `/results` | ~20s | 4.3s | **4.2s** ✓ |
| `/structures`(50 个 PDB) | **524 (>125s)** | 4.7s | **0.20s** ✓ |
| `/sequences` | ~16s | — | **4.1s** ✓ |
| `/download`(打包全部文件) | **524 (>125s)** | — | **1.9s** ✓(1.25 MB ZIP) |

## 6. 这是全集群隐患 + 尚未做的根治

`ndots:2` 只修了 `astramolecula-backend` 这**一个** Deployment。泄漏的外部 `search` 域影响**全集群**:任何"按调用新建连接(非连接池)"的服务,只要用内部 FQDN,都会吃这 ~8s。

- **建议同样加 `ndots:2`** 的对象:其它 astramolecula compute(`highfold-c2c`/`dockingvina`/`peptide-opt`/`autosarm`/`dmat`)、以及 aidd-agent 里按调用访问 SeaweedFS 的地方。
- **彻底根治(未做)**:清掉节点 `/etc/resolv.conf` 里泄漏的外部 `search` 域,或给 k3s kubelet 配 `--resolv-conf` 指向一份干净的 resolv.conf。这会让全集群所有 pod 受益,但 blast radius 大,需谨慎验证。

## 7. 如何复现 / 快速诊断

```bash
# A. 公网分层计时(轻 DB 端点 vs 重存储端点),区分 DB 层 vs 存储层
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
  -H "X-API-Key: <key>" -H "X-External-User-ID: <id>" \
  "https://api.genionaitech.com/highfold/<task_id>/params"     # 快 → DB 正常
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" ... \
  "https://api.genionaitech.com/highfold/<task_id>/structures" # 慢/524 → 存储层

# B. 集群内确认 DNS(关键):8s vs 0s = 命中本根因
kubectl exec -n astramolecula <backend-pod> -- python3 -c \
 'import socket,time; n="aidd-seaweedfs-filer.aidd-agent.svc.cluster.local";
  t=time.time(); socket.gethostbyname(n); print("no-dot", round(time.time()-t,3));
  t=time.time(); socket.gethostbyname(n+"."); print("trailing-dot", round(time.time()-t,3))'
# no-dot ~8s 且 trailing-dot ~0s → 就是 ndots/search 域问题
kubectl exec -n astramolecula <backend-pod> -- cat /etc/resolv.conf   # 看 search 是否含外部域
```

## 8. 附带发现(安全,建议单独跟进)

排查中确认:后端**未设 `SERVICE_API_KEYS` 环境变量**,生效的就是 `core/config/settings.yaml` 里的占位 key(`third-party-service-key-123` / `another-service-key-456` / `test-api-key-789`);DB 密码仅 6 位;`astramolecula-secrets` 也没有 `JWT_SECRET_KEY`(JWT secret 大概率也是占位)。建议用强随机值经 env/secret 覆盖并轮换。详见仓库安全待办。

## 9. 相关

- 同一客户工单的**另一个、独立的**根因(漏 `/api` 前缀 → 前端 SPA 返回 `index.html`),见前端仓库 `AstraMolecula-front/docs/API_PATH_SPA_FALLBACK_FIX.md`。
- 代码:`src/astra_molecula/services/storage/seaweed_storage.py`、`src/astra_molecula/services/highfold_results.py`。
- DNS 配置:`infra/k3s-manifests/apps/astramolecula/astramolecula-backend.yaml`。
