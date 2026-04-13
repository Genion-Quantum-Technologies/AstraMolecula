# AstraMolecula 网络架构文档

> 最后更新: 2026-03-30

## 1. 整体架构概览

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              用户浏览器                                       │
│                                                                              │
│   前端访问: https://platform.genionaitech.com                                │
│   API访问:  https://api.genionaitech.com                                     │
└──────────────┬──────────────────────────────────┬────────────────────────────┘
               │                                  │
               ▼                                  ▼
┌──────────────────────────┐        ┌──────────────────────────────────────────┐
│   AWS CloudFront CDN     │        │   AWS EC2 (3.133.131.124)                │
│                          │        │   Nginx 反向代理 (HTTPS/443)              │
│   platform.genionaitech  │        │   api.genionaitech.com                   │
│   .com                   │        │                                          │
│                          │        │   ┌─────────────────────────────────┐    │
│   Origin:                │        │   │  upstream backend → 127.0.0.1: │    │
│   3.133.131.124:3000     │───────▶│   │  8000 (autossh 隧道)           │    │
│                          │        │   │                                 │    │
│                          │        │   │  upstream frontend → 127.0.0.1:│    │
│                          │        │   │  3000 (autossh 隧道)           │    │
│                          │        │   └─────────────────────────────────┘    │
└──────────────────────────┘        └──────────┬──────────────┬────────────────┘
                                               │              │
                                    autossh -R 8000           │ autossh -R 3000
                                               │              │
                                               ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     本地服务器 (genion-computing)                              │
│                                                                              │
│  ┌─────────────────────┐  ┌───────────────────┐  ┌───────────────────────┐  │
│  │ astramolecula-test   │  │ astra-frontend    │  │ SeaweedFS 集群        │  │
│  │ (后端 API)           │  │ -nginx (前端)     │  │                       │  │
│  │                      │  │                   │  │  master  → :9333      │  │
│  │ Docker:              │  │ Docker:           │  │  volume  → :8080      │  │
│  │ 0.0.0.0:8001→8000   │  │ 0.0.0.0:80→80    │  │  filer   → :8888      │  │
│  │                      │  │                   │  │  s3      → :8333      │  │
│  └──────────┬───────────┘  └───────┬───────────┘  └───────────────────────┘  │
│             │                      │                         ▲               │
│             │ /api/ proxy          │                         │               │
│             │ → host.docker.       │                         │               │
│             │   internal:8001      │                upload_bytes             │
│             └──────────────────────┘                (filer:8888)             │
│                                                                              │
│  ┌───────────────────┐  ┌───────────────────────────────────────────────┐   │
│  │ PostgreSQL         │  │ docker-app-1 (autoSARM)                      │   │
│  │ :5432              │  │ :8003                                         │   │
│  └───────────────────┘  └───────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. 域名配置

| 域名 | DNS 解析 | 用途 | HTTPS |
|------|---------|------|-------|
| `api.genionaitech.com` | A记录 → `3.133.131.124` (AWS EC2) | 后端API直接访问 | ✅ Nginx SSL (Let's Encrypt 通配符证书) |
| `platform.genionaitech.com` | CNAME → `d31nbszkjh476e.cloudfront.net` (CloudFront) | 前端Web应用 | ✅ CloudFront 托管 SSL |
| `platform-dev.genionaitech.com` | (开发环境) | 开发前端 | ✅ |

### SSL 证书

- **类型**: Let's Encrypt 通配符证书 (`*.genionaitech.com`)
- **签发方式**: acme.sh + GoDaddy DNS 验证
- **证书位置** (本地): `SSL/fullchain.cer`, `SSL/_.genionaitech.com.key`
- **证书位置** (AWS): `/etc/nginx/ssl/genionaitech.com.crt`, `/etc/nginx/ssl/genionaitech.com.key`
- **当前有效期**: 至 2026-04-20 (每90天需续签)
- **密钥算法**: EC P-256 (`ec-256`)

## 3. 本地 Docker 容器

| 容器名 | 镜像 | 端口映射 | 功能 |
|--------|------|---------|------|
| `astramolecula-test` | `astramolecula:latest` | `0.0.0.0:8001→8000` | AstraMolecula 后端API (FastAPI/Uvicorn) |
| `astra-frontend-nginx` | `astra-molecula-frontend:latest` | `0.0.0.0:80→80` | React前端 (Nginx 静态文件+API代理) |
| `docker-app-1` | `docker-app` | `0.0.0.0:8003→8003` | autoSARM 服务 |
| `postgres-container` | `postgres` | `0.0.0.0:5432→5432` | PostgreSQL 数据库 |
| `local_seaweedfs-master-1` | `chrislusf/seaweedfs` | `0.0.0.0:9333→9333` | SeaweedFS Master |
| `local_seaweedfs-volume-1` | `chrislusf/seaweedfs` | `0.0.0.0:8080→8080` | SeaweedFS Volume |
| `local_seaweedfs-filer-1` | `chrislusf/seaweedfs` | `0.0.0.0:8888→8888` | SeaweedFS Filer (文件上传入口) |
| `local_seaweedfs-s3-1` | `chrislusf/seaweedfs` | `0.0.0.0:8333→8333` | SeaweedFS S3 Gateway |

### Docker Compose 文件位置

| 服务 | 文件路径 |
|------|---------|
| AstraMolecula 后端 | `AstraMolecula/cicd/docker/docker-compose.dev.yml` |
| AstraMolecula 前端 | `AstraMolecula-front/docker-compose.yml` |
| SeaweedFS | `local_seaweedfs/docker-compose.yml` |
| autoSARM | `autoSARM/docker-compose.yml` |

## 4. AutoSSH 反向隧道

通过 AutoSSH 将本地服务暴露到 AWS EC2 服务器上，让外网可以通过域名访问本地服务。

| 隧道 | 本地端口 | AWS远端端口 | 用途 |
|------|---------|------------|------|
| 后端隧道 | `localhost:8001` | `0.0.0.0:8000` | AstraMolecula 后端 API |
| 前端隧道 | `localhost:80` | `0.0.0.0:3000` | React 前端应用 |

### AutoSSH 参数

```bash
# 后端隧道
autossh -M 0 -N \
  -i ~/.ssh/id_ed25519 \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -R 0.0.0.0:8000:localhost:8001 \
  ubuntu@3.133.131.124

# 前端隧道
autossh -M 0 -N \
  -i ~/.ssh/id_ed25519 \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -R 0.0.0.0:3000:localhost:80 \
  ubuntu@3.133.131.124
```

### 启动脚本

- 后端: `AstraMolecula/cicd/scripts/setup_autossh.sh`
- 前端: `AstraMolecula-front/deploy/setup_frontend_autossh.sh`

## 5. AWS EC2 Nginx 配置

- **配置文件**: `/etc/nginx/sites-available/astramolecula`
- **域名**: `api.genionaitech.com`

### Upstream 定义

```nginx
upstream astramolecula_backend {
    server 127.0.0.1:8000;   # ← autossh 后端隧道
    keepalive 32;
}

upstream astramolecula_frontend {
    server 127.0.0.1:3000;   # ← autossh 前端隧道
    keepalive 32;
}
```

### 路由表

| 路径 | 代理目标 | 认证 | CORS | 说明 |
|------|---------|------|------|------|
| `/` | backend (:8000) | 需要 | 动态 CORS | 主API入口 |
| `/health` | backend (:8000) | 不需要 | - | 健康检查 |
| `/docs`, `/openapi.json`, `/redoc` | backend (:8000) | 不需要 | - | API文档 |
| `/upload_pdbqt`, `/uploads` | backend (:8000) | 需要 | 动态 CORS | 文件上传 (max 100MB) |
| `/public/(docking\|peptide)/` | backend (:8000) | 不需要 | `*` | 公开 API |
| `/public/(docking-viewer\|peptide-viewer)` | frontend (:3000) | 不需要 | `*`, 允许 iframe | 公开查看器页面 |
| `/api/public/` | frontend (:3000) | 不需要 | `*` | 前端代理的公开路径 |
| `/static/` | frontend (:3000) | 不需要 | `*` | 静态资源 (缓存1年) |

### 动态 CORS 策略

Nginx 使用 `map` 指令根据请求 Origin 动态设置 CORS 头：

| 请求来源 | `Access-Control-Allow-Origin` | `Access-Control-Allow-Credentials` |
|---------|-------------------------------|-----------------------------------|
| `https://platform.genionaitech.com` | 回显具体 Origin | `true` |
| `https://platform-dev.genionaitech.com` | 回显具体 Origin | `true` |
| `http://localhost:3000` | 回显具体 Origin | `true` |
| 其他来源 | `*` | 不设置 |

## 6. 前端 Nginx (Docker 容器内)

- **容器**: `astra-frontend-nginx`
- **配置文件**: `/etc/nginx/conf.d/default.conf`

### API 代理

```nginx
location /api/ {
    proxy_pass http://host.docker.internal:8001/;  # 宿主机上的后端容器
    ...
}
```

> 注意: 前端容器内的 `/api/` 代理直接指向宿主机 `host.docker.internal:8001`，
> 对应 `astramolecula-test` 容器的端口映射 `8001→8000`。

### 前端 API 配置

```typescript
// AstraMolecula-front/src/api/config.ts
export const API_BASE_URL = process.env.NODE_ENV === 'development'
  ? (process.env.REACT_APP_API_BASE_URL || '/api')
  : '/api';   // 生产环境: 相对路径，由 nginx 代理
```

## 7. CloudFront CDN

- **分发域名**: `d31nbszkjh476e.cloudfront.net`
- **绑定域名**: `platform.genionaitech.com`
- **Origin**: `3.133.131.124:3000` (AWS EC2 上的前端隧道端口)

### 请求链路（前端访问 API）

```
用户浏览器
  → https://platform.genionaitech.com/api/upload_pdbqt
  → CloudFront → 3.133.131.124:3000 (前端 nginx)
  → 前端 nginx /api/ → proxy_pass http://host.docker.internal:8001/ (经 autossh)
  → 后端 FastAPI /upload_pdbqt
  → SeaweedFS filer (172.17.0.1:8888)
```

### 请求链路（直接 API 访问）

```
外部客户端/第三方
  → https://api.genionaitech.com/upload_pdbqt
  → AWS EC2 Nginx (443) → 127.0.0.1:8000 (autossh 隧道)
  → 本地 Docker astramolecula-test:8001 → 内部 :8000
  → 后端 FastAPI /upload_pdbqt
  → SeaweedFS filer (172.17.0.1:8888)
```

## 8. 存储服务 (SeaweedFS)

- **Docker Compose**: `local_seaweedfs/docker-compose.yml`
- **Filer 端点**: `http://172.17.0.1:8888` (Docker 宿主机网关)

### 组件

| 组件 | 端口 | 管理端口 | 功能 |
|------|------|---------|------|
| Master | 9333 | 19333 | 集群协调 |
| Volume | 8080 | 18080 | 数据存储 |
| Filer | 8888 | 18888 | 文件系统接口 (上传/下载入口) |
| S3 | 8333 | - | S3 兼容接口 |

### 后端存储配置

```python
# AstraMolecula 后端环境变量
SEAWEED_FILER_ENDPOINT=http://172.17.0.1:8888
```

文件上传路径: `uploads/{user_id}/{filename}` → SeaweedFS Filer

## 9. 数据库

- **类型**: PostgreSQL
- **容器**: `postgres-container`
- **端口**: `0.0.0.0:5432→5432`
- **初始化脚本**: `AstraMolecula/database/init_database_postgres.sql`

## 10. 认证体系

### JWT Token 认证 (前端用户)

```
前端登录 → POST /login → 返回 JWT Token
后续请求 → Authorization: Bearer <token>
```

### API Key 认证 (服务间调用)

```
Header: X-API-Key: <service_api_key>
Header: X-External-User-ID: <external_user_id>
```

### 中间件开放路径 (无需认证)

```
精确匹配: /, /health, /login, /signup, /docs, /openapi.json, /redoc, /smiles2img, /fragmentize, /logs
前缀匹配: /static/*, /public/*, /api/public/*
```

## 11. 端口分配总表

| 端口 | 服务 | 位置 | 说明 |
|------|------|------|------|
| 80 | 前端 Nginx | 本地 Docker + AWS (HTTP→HTTPS重定向) | 前端Web应用 |
| 443 | Nginx SSL | AWS EC2 | HTTPS API入口 |
| 3000 | 前端隧道 | AWS EC2 (autossh) | CloudFront Origin → 本地 :80 |
| 5432 | PostgreSQL | 本地 Docker | 数据库 |
| 8000 | 后端隧道 | AWS EC2 (autossh) | Nginx upstream → 本地 :8001 |
| 8001 | AstraMolecula 后端 | 本地 Docker (→容器内 :8000) | FastAPI 应用 |
| 8003 | autoSARM | 本地 Docker | autoSARM 服务 |
| 8080 | SeaweedFS Volume | 本地 Docker | 数据存储 |
| 8333 | SeaweedFS S3 | 本地 Docker | S3 兼容接口 |
| 8888 | SeaweedFS Filer | 本地 Docker | 文件系统接口 |
| 9333 | SeaweedFS Master | 本地 Docker | 集群协调 |

## 12. 常见运维操作

### 重启 SeaweedFS

```bash
cd /home/songyou/projects/local_seaweedfs
sudo docker compose up -d
```

### 重启后端容器

```bash
sudo docker restart astramolecula-test
```

### 重启前端容器

```bash
sudo docker restart astra-frontend-nginx
```

### 检查 AutoSSH 隧道

```bash
ps aux | grep autossh | grep -v grep
```

### 重建 AutoSSH 隧道

```bash
# 后端
bash AstraMolecula/cicd/scripts/setup_autossh.sh start

# 前端
bash AstraMolecula-front/deploy/setup_frontend_autossh.sh start
```

### 续签 SSL 证书

```bash
# 在有 acme.sh 的机器上
acme.sh --renew -d "*.genionaitech.com" --ecc

# 上传到 AWS EC2
scp fullchain.cer ubuntu@3.133.131.124:/etc/nginx/ssl/genionaitech.com.crt
scp _.genionaitech.com.key ubuntu@3.133.131.124:/etc/nginx/ssl/genionaitech.com.key

# 重载 nginx
ssh ubuntu@3.133.131.124 'sudo nginx -t && sudo systemctl reload nginx'
```

### 修改 AWS Nginx 配置

```bash
# 编辑
ssh ubuntu@3.133.131.124 'sudo nano /etc/nginx/sites-available/astramolecula'

# 测试并重载
ssh ubuntu@3.133.131.124 'sudo nginx -t && sudo systemctl reload nginx'
```

## 13. 故障排查

| 症状 | 可能原因 | 排查命令 |
|------|---------|---------|
| 502 Bad Gateway (api.genionaitech.com) | AutoSSH 隧道断开 | `ssh ubuntu@3.133.131.124 'curl -s http://127.0.0.1:8000/health'` |
| 502 Bad Gateway (platform.genionaitech.com) | 前端隧道断开或前端容器停止 | `ssh ubuntu@3.133.131.124 'curl -s http://127.0.0.1:3000/health'` |
| 上传文件 500 错误 | SeaweedFS 未运行 | `curl -s http://localhost:8888/` |
| AUTH_MIDDLEWARE_ERROR | 中间件 catch-all — 查看具体异常 | `sudo docker logs astramolecula-test --tail 50` |
| SSL 证书过期 | 通配符证书每90天需续签 | `openssl x509 -enddate -noout -in SSL/fullchain.cer` |
| CloudFront 502 | AWS nginx 或后端不可达 | `curl -sI https://api.genionaitech.com/health` |
