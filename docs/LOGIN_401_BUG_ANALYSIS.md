# Login 401 问题诊断报告

> 时间: 2026-04-02

## 问题描述

用户在 `https://platform.genionaitech.com` 上使用账号密码登录时，收到如下错误：

```json
{
  "error": "Authentication required",
  "message": "This endpoint requires authentication. Please provide a valid Bearer token or API key.",
  "error_code": "AUTH_MISSING_CREDENTIALS"
}
```

## 诊断结论

**根因：CloudFront 将 `/api/*` 请求路由到了 AWS EC2 的 443 端口（AWS Nginx），而不是前端隧道端口 3000。导致后端收到的路径是 `/api/login` 而非 `/login`，中间件未放行，返回 401。**

---

## 诊断过程

### 1. 后端日志确认实际请求路径

```bash
sudo docker logs astramolecula-test --tail 100 | grep -i "login\|Unauthenticated\|protected path"
```

**关键日志输出：**
```
2026-04-02 12:48:44 | WARNING | middleware.py:156 | Unauthenticated request to protected path: /api/login
```

> 后端收到的路径是 `/api/login`，而中间件的开放路径 `OPEN_PATHS` 中只有 `/login`，两者不匹配，直接返回 401。

---

### 2. 各链路测试结果

| 测试路径 | 方式 | HTTP 状态 | 响应 path 字段 | 结论 |
|---------|------|-----------|--------------|------|
| `localhost:80/api/login` | 本地前端 nginx | 401 (密码错误) | `/login` | ✅ 前端 nginx 正确剥离 `/api/` |
| `localhost:8001/login` | 本地后端直连 | 401 (密码错误) | `/login` | ✅ 后端 `/login` 端点正常 |
| `localhost:8001/api/login` | 本地后端直连 | 401 | `AUTH_MISSING_CREDENTIALS` | ❌ 复现问题 |
| EC2 `127.0.0.1:3000/api/login` | 前端隧道 | 401 (密码错误) | `/login` | ✅ 前端隧道链路正常 |
| EC2 `127.0.0.1:8000/api/login` | 后端隧道 | 401 | `AUTH_MISSING_CREDENTIALS` | ❌ 复现问题 |
| `api.genionaitech.com/login` | AWS Nginx 直连 | 401 (密码错误) | `/login` | ✅ AWS Nginx → 后端正常 |
| `api.genionaitech.com/api/login` | AWS Nginx 直连 | 401 | `AUTH_MISSING_CREDENTIALS` | ❌ 复现问题 |
| `platform.genionaitech.com/api/login` | CloudFront | 401 | `AUTH_MISSING_CREDENTIALS` | ❌ **线上问题** |

---

### 3. 关键响应头分析

对 `platform.genionaitech.com/api/login` 的请求，响应头如下：

```
HTTP/2 401
server: nginx/1.24.0 (Ubuntu)          ← AWS EC2 的 Nginx，不是前端容器
access-control-allow-origin: *          ← AWS Nginx location / 的默认 CORS
x-cache: Error from cloudfront          ← 经过了 CloudFront
via: 1.1 c35af9913ec186d5ecdb304dc720b006.cloudfront.net (CloudFront)
```

- `server: nginx/1.24.0 (Ubuntu)` 说明请求被转发给了 **AWS EC2 的 Nginx**（端口 443），而不是前端 nginx 容器（端口 3000/80）
- 如果走正确的前端 nginx 链路，响应应由前端 nginx 或后端处理，`server` 头会不同，且 CORS origin 应为 `https://platform.genionaitech.com`（因为 Origin 在白名单中）

---

## 完整请求链路对比

### 正确链路（期望）

```
浏览器 POST https://platform.genionaitech.com/api/login
  ↓
CloudFront (CNAME → d31nbszkjh476e.cloudfront.net)
  ↓  Origin: 3.133.131.124:3000
AWS EC2 前端隧道 :3000
  ↓  autossh -R 0.0.0.0:3000:localhost:80
本地前端 nginx 容器 :80
  ↓  location /api/ { proxy_pass http://host.docker.internal:8001/; }
     → 剥离 /api/ 前缀
本地后端容器 :8001 (内部 :8000)
  ↓  request.url.path = "/login"  → 命中 OPEN_PATHS → ✅ 放行
FastAPI /login 处理
```

### 实际链路（有问题）

```
浏览器 POST https://platform.genionaitech.com/api/login
  ↓
CloudFront
  ↓  /api/* 行为规则 → Origin: 3.133.131.124:443  ← 问题所在
AWS EC2 Nginx :443 (api.genionaitech.com)
  ↓  location / { proxy_pass http://astramolecula_backend; }
     → 原样转发，路径仍为 /api/login
AWS EC2 后端隧道 :8000
  ↓  autossh → 本地后端 :8001
本地后端容器 :8001
  ↓  request.url.path = "/api/login"  → 不在 OPEN_PATHS → ❌ 返回 401
```

---

## 受影响的端点

所有通过 `platform.genionaitech.com` 访问的前端 API 调用，凡是路径以 `/api/` 开头的，理论上都走了错误的链路。登录尤为明显，因为它未携带 Bearer Token，中间件直接拦截。

已登录用户（携带 Token）的请求虽然也走了错误的 `/api/*` 路径，但中间件会验证 Token，如果 Token 有效则可以通过，不会出现 401——但请求的路径到达后端是 `/api/xxx` 而非 `/xxx`，可能导致 FastAPI 路由找不到对应端点（取决于后端路由注册方式）。

---

## 修复方案

### 方案 A：修改 CloudFront 配置（推荐，根治）

**操作：** 登录 AWS Console → CloudFront → 找到 `platform.genionaitech.com` 对应的分发 → 查看 **Behaviors（行为）** 配置。

如果存在 `/api/*` 的 Cache Behavior 指向了 `api.genionaitech.com:443`（或 `3.133.131.124:443`）的 Origin：
- **删除该 Behavior**，让所有请求统一走默认 Behavior（Origin 为 `3.133.131.124:3000`）
- 或将该 Behavior 的 Origin 改为 `3.133.131.124:3000`（前端隧道端口）

**效果：** 所有请求（包括 `/api/*`）都经过前端 nginx，由前端 nginx 的 `location /api/` 剥离前缀后再转发给后端，后端收到正确的路径。

---

### 方案 B：修改后端中间件 OPEN_PATHS（快速修复）

在 `src/astra_molecula/middleware.py` 中，将 `/api/login` 和 `/api/signup` 加入 `OPEN_PATHS`：

```python
OPEN_PATHS = {
    "/",
    "/health",
    "/login",
    "/signup",
    "/api/login",    # 新增：兼容未剥离 /api/ 前缀的请求
    "/api/signup",   # 新增：兼容未剥离 /api/ 前缀的请求
    "/docs",
    "/openapi.json",
    "/redoc",
    "/smiles2img",
    "/fragmentize",
    "/logs",
}
```

**缺点：**
- 仅解决登录/注册问题，其他已认证 API（如 `/api/docking`、`/api/peptide`）若走错误链路，FastAPI 路由可能仍无法匹配
- 治标不治本，推荐仅作临时应急措施

---

### 方案 C：中间件路径归一化（代码层兼容）

在中间件中添加路径归一化逻辑，自动剥离 `/api/` 前缀再做路径匹配（仅用于 OPEN_PATHS 判断，不修改实际请求路径）：

```python
# 在 auth_middleware 中，路径检查前做归一化
path = request.url.path
normalized_path = path.removeprefix("/api") if path.startswith("/api/") else path

if normalized_path in OPEN_PATHS or normalized_path.startswith(OPEN_PATH_PREFIXES):
    return await call_next(request)
```

**缺点：** 仍无法解决 FastAPI 路由不匹配的问题（FastAPI 路由注册的是 `/login`，收到 `/api/login` 时虽然过了中间件，但路由层会 404）。

---

## 推荐操作顺序

1. **立即**：在 AWS CloudFront 控制台检查并修正 `/api/*` 的 Behavior 配置（方案 A）
2. **验证**：修改后执行 `curl -sv -X POST "https://platform.genionaitech.com/api/login" ...`，确认响应头 `server` 不再是 AWS Nginx，且登录成功
3. **可选**：如需兼容两种链路，再叠加方案 B 作为保险

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `src/astra_molecula/middleware.py` | 后端认证中间件，`OPEN_PATHS` 定义 |
| `AstraMolecula-front/docker/default.conf` | 前端 nginx 配置，`location /api/` 剥除前缀 |
| `/etc/nginx/sites-available/astramolecula` | AWS EC2 Nginx 配置（服务器上）|
| AWS CloudFront 控制台 | 分发 `d31nbszkjh476e.cloudfront.net` 的 Behavior 配置 |
