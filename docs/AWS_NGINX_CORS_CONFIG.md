# AWS EC2 Nginx CORS 配置说明

## 概述

本文档说明 AWS EC2 服务器上 AstraMolecula 服务的 Nginx 配置，特别是动态 CORS（跨域资源共享）的实现方案。

**服务器信息**：
- 主机：`3.133.131.124` (ec2-us)
- 域名：`api.genionaitech.com`
- 配置文件：`/etc/nginx/sites-available/astramolecula`

## 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户浏览器                                  │
│  platform.genionaitech.com / platform-dev.genionaitech.com          │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTPS (443)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AWS EC2 Nginx (api.genionaitech.com)             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    动态 CORS 处理                            │   │
│  │  - 已知域名 → 返回具体 Origin + Credentials                  │   │
│  │  - 其他来源 → 返回 * (兼容第三方 API 调用)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│              ┌───────────────┴───────────────┐                     │
│              ▼                               ▼                      │
│     autossh 反向代理                  autossh 反向代理              │
│     127.0.0.1:8001                   127.0.0.1:3000                 │
└──────────────┬───────────────────────────────┬──────────────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   本地后端 (AstraMolecula)│    │   本地前端 (React)       │
│   Docker: 8001 → 8000    │    │   Docker: 3000 → 80      │
└──────────────────────────┘    └──────────────────────────┘
```

## 动态 CORS 配置

### 设计目标

1. **前端应用支持**：允许 `platform.genionaitech.com` 和 `platform-dev.genionaitech.com` 携带认证信息（credentials）访问 API
2. **第三方 API 兼容**：保持对第三方服务的 `Access-Control-Allow-Origin: *` 支持
3. **安全性**：仅对已知域名启用 `Access-Control-Allow-Credentials: true`

### 实现方式

使用 Nginx 的 `map` 指令根据请求的 `Origin` 头动态设置 CORS 响应头：

```nginx
# 动态 CORS Origin 映射
map $http_origin $cors_origin {
    default "*";                                    # 其他来源返回 *
    "https://platform.genionaitech.com" $http_origin;
    "https://platform-dev.genionaitech.com" $http_origin;
    "http://localhost:3000" $http_origin;
    "http://127.0.0.1:3000" $http_origin;
}

# 动态 Credentials 映射
map $http_origin $cors_credentials {
    default "";                                     # 其他来源不设置
    "https://platform.genionaitech.com" "true";
    "https://platform-dev.genionaitech.com" "true";
    "http://localhost:3000" "true";
    "http://127.0.0.1:3000" "true";
}
```

### CORS 响应对比

| 请求来源 | `Access-Control-Allow-Origin` | `Access-Control-Allow-Credentials` |
|---------|-------------------------------|-----------------------------------|
| `https://platform.genionaitech.com` | `https://platform.genionaitech.com` | `true` |
| `https://platform-dev.genionaitech.com` | `https://platform-dev.genionaitech.com` | `true` |
| `http://localhost:3000` | `http://localhost:3000` | `true` |
| 其他第三方来源 | `*` | 不设置 |

## 路由配置

### 主要 API 路由 (`/`)

- **目标**：后端服务 (`127.0.0.1:8001`)
- **CORS**：动态配置（支持 credentials）
- **用途**：认证 API、任务管理、文件上传等

```nginx
location / {
    proxy_pass http://astramolecula_backend;
    
    # 动态 CORS 头
    add_header Access-Control-Allow-Origin $cors_origin always;
    add_header Access-Control-Allow-Credentials $cors_credentials always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Authorization, X-API-Key, X-External-User-ID, Content-Type, Accept" always;
}
```

### 公开 Viewer 页面 (`/public/docking-viewer`, `/public/peptide-viewer`)

- **目标**：前端服务 (`127.0.0.1:3000`)
- **CORS**：`Access-Control-Allow-Origin: *`
- **特性**：允许 iframe 嵌入（无 X-Frame-Options）
- **用途**：第三方网站嵌入 3D 分子查看器

### 公开 API 路径 (`/public/docking/*`, `/public/peptide/*`)

- **目标**：后端服务
- **CORS**：`Access-Control-Allow-Origin: *`
- **用途**：无需认证的公开 API 接口

### 静态资源 (`/static/*`)

- **目标**：前端服务
- **缓存**：1 年长期缓存
- **CORS**：`Access-Control-Allow-Origin: *`

### 文件上传 (`/uploads/*`, `/api/*upload`)

- **目标**：后端服务
- **CORS**：动态配置
- **特性**：禁用请求缓冲、300秒超时
- **限制**：最大 100MB

## 允许的请求头

```
Authorization      - JWT Token 认证
X-API-Key          - 第三方 API Key 认证
X-External-User-ID - 第三方用户标识
Content-Type       - 内容类型
Accept             - 接受类型
```

## 安全配置

### SSL/TLS

- 协议：TLSv1.2, TLSv1.3
- 证书路径：`/etc/nginx/ssl/genionaitech.com.crt`
- 密钥路径：`/etc/nginx/ssl/genionaitech.com.key`

### 安全头

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;  # 仅主 API
```

## 常用命令

### 测试配置

```bash
ssh ec2-us "sudo nginx -t"
```

### 重载配置

```bash
ssh ec2-us "sudo systemctl reload nginx"
```

### 查看配置

```bash
ssh ec2-us "cat /etc/nginx/sites-available/astramolecula"
```

### 查看日志

```bash
ssh ec2-us "sudo tail -f /var/log/nginx/astramolecula.access.log"
ssh ec2-us "sudo tail -f /var/log/nginx/astramolecula.error.log"
```

### 测试 CORS

```bash
# 测试已知域名（应返回具体 Origin + credentials: true）
curl -sI -X OPTIONS "https://api.genionaitech.com/tasks/" \
  -H "Origin: https://platform.genionaitech.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control"

# 测试第三方来源（应返回 *）
curl -sI -X OPTIONS "https://api.genionaitech.com/tasks/" \
  -H "Origin: https://some-third-party.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control"
```

## 备份与恢复

### 备份位置

配置文件备份：`/etc/nginx/sites-available/astramolecula.backup.YYYYMMDD`

### 恢复配置

```bash
ssh ec2-us "sudo cp /etc/nginx/sites-available/astramolecula.backup.20260128 /etc/nginx/sites-available/astramolecula"
ssh ec2-us "sudo nginx -t && sudo systemctl reload nginx"
```

## 添加新的 CORS 白名单域名

如需添加新域名到 CORS 白名单，编辑配置文件中的 `map` 块：

```nginx
map $http_origin $cors_origin {
    default "*";
    "https://platform.genionaitech.com" $http_origin;
    "https://platform-dev.genionaitech.com" $http_origin;
    "https://new-domain.example.com" $http_origin;  # 新增
    # ...
}

map $http_origin $cors_credentials {
    default "";
    "https://platform.genionaitech.com" "true";
    "https://platform-dev.genionaitech.com" "true";
    "https://new-domain.example.com" "true";  # 新增
    # ...
}
```

然后重载配置：

```bash
ssh ec2-us "sudo nginx -t && sudo systemctl reload nginx"
```

## 更新日志

| 日期 | 变更内容 |
|------|---------|
| 2026-01-28 | 添加动态 CORS 配置，支持 `platform.genionaitech.com` 和 `platform-dev.genionaitech.com` |
| 2026-01-21 | 初始 SSL 配置 |
