# DockingVina CI/CD 文档和脚本

这个目录包含了DockingVina服务的所有CI/CD相关文件，包括部署脚本、Docker配置和相关文档。

## 📂 目录结构

```
cicd/
├── scripts/                    # 部署和管理脚本
│   ├── deploy.sh              # 主部署脚本
│   ├── start_docking_service.sh  # 服务管理脚本
│   ├── setup_autossh.sh       # AutoSSH隧道脚本
│   ├── nginx_setup.sh         # Nginx配置脚本
│   ├── aliyun_setup.sh        # 阿里云专用配置
│   ├── quick_config.sh        # 快速配置工具
│   └── test_connection.sh     # 连接测试脚本
├── docs/                      # 文档
│   └── DEPLOYMENT_GUIDE.md    # 部署指南
├── docker/                    # Docker相关文件
│   ├── Dockerfile            # Docker镜像构建文件
│   └── .dockerignore        # Docker忽略文件
└── .github/                   # GitHub Actions工作流
    └── workflows/
        └── github-actions-demo.yml
```

## 🚀 快速开始

### 方式一：使用快捷脚本（推荐）

在项目根目录下，可以直接使用快捷脚本：

```bash
# 部署管理
./deploy start          # 启动所有服务
./deploy stop           # 停止所有服务
./deploy status         # 查看状态
./deploy logs           # 查看日志

# 服务管理
./service start         # 启动DockingVina服务
./service stop          # 停止DockingVina服务
./service status        # 查看服务状态
```

### 方式二：直接使用CI/CD脚本

```bash
# 进入脚本目录
cd cicd/scripts/

# 快速配置
./quick_config.sh

# 完整部署
./deploy.sh start
```

## 📋 脚本功能说明

### 核心脚本

| 脚本 | 功能 | 用途 |
|------|------|------|
| `deploy.sh` | 主部署脚本 | 统一管理所有服务的部署 |
| `start_docking_service.sh` | 服务管理 | 管理DockingVina API服务 |
| `setup_autossh.sh` | 隧道管理 | 建立SSH反向隧道 |
| `nginx_setup.sh` | 代理配置 | 配置云服务器Nginx |

### 配置脚本

| 脚本 | 功能 | 用途 |
|------|------|------|
| `quick_config.sh` | 快速配置 | 一键配置基本参数 |
| `aliyun_setup.sh` | 阿里云配置 | 阿里云ECS专用配置 |
| `test_connection.sh` | 连接测试 | 验证各项连接 |

## 🔧 配置说明

### 环境变量

主要配置文件在各脚本顶部：

```bash
# 项目路径
PROJECT_DIR="/home/davis/projects/genion_quantum/AstraMolecula"

# 云服务器配置
CLOUD_SERVER="106.14.212.218"
CLOUD_USER="root"
SSH_KEY_PATH="$HOME/.ssh/pc_wsl2ecs.pem"

# 服务端口
LOCAL_DOCKING_PORT=8000
REMOTE_DOCKING_PORT=8000
```

### 部署流程

1. **环境检查**: `./deploy.sh check`
2. **配置参数**: `./quick_config.sh` 或 `./deploy.sh config`
3. **启动服务**: `./deploy.sh start`
4. **验证部署**: `./deploy.sh status` 和 `./deploy.sh test`

## 📖 详细文档

更详细的部署说明请参考：[部署指南](docs/DEPLOYMENT_GUIDE.md)

## 🐛 故障排除

### 常见问题

1. **权限问题**: 确保所有脚本有执行权限
   ```bash
   chmod +x cicd/scripts/*.sh
   ```

2. **路径问题**: 脚本已配置相对路径，可在项目任意位置运行

3. **SSH连接**: 使用 `./setup_autossh.sh test` 验证SSH连接

4. **服务状态**: 使用 `./deploy.sh status` 查看服务状态

### 日志位置

- DockingVina服务: `logs/docking_service.log`
- AutoSSH隧道: `~/logs/autossh_docking.log`

## 🔄 更新记录

- 重构CI/CD目录结构
- 修复脚本路径引用
- 添加快捷访问脚本
- 统一配置管理

---

*最后更新: 2025年8月*
