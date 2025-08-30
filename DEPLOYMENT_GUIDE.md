# DockingVina服务部署指南

本指南帮助您在WSL环境中部署DockingVina服务，并通过AutoSSH建立到云服务器的反向代理，实现外网访问。

## 📋 部署架构

```
外网用户 → 云服务器Nginx → AutoSSH隧道 → WSL中的DockingVina服务
```

## 🛠️ 环境要求

### WSL环境
- Ubuntu 20.04+ 或其他Linux发行版
- Anaconda/Miniconda
- AutoSSH
- SSH密钥对

### 云服务器
- Ubuntu/CentOS/RHEL/Fedora
- Nginx
- 开放80/443端口

## 🚀 快速部署

### 方式一：使用快速配置工具（推荐）
```bash
cd /home/davis/projects/AstraMolecula/dockingVina
./quick_config.sh
```
按提示输入云服务器用户名，脚本会自动配置IP地址：106.14.212.218

### 方式二：手动配置
#### 第一步：环境检查
```bash
cd /home/davis/projects/AstraMolecula/dockingVina
./deploy.sh check
```

#### 第二步：配置连接参数
```bash
./deploy.sh config
```
按提示输入：
- 云服务器IP：106.14.212.218（已预配置）
- 云服务器用户名
- SSH密钥路径

#### 第三步：启动服务
```bash
./deploy.sh start
```

#### 第四步：验证部署
```bash
./deploy.sh status
./deploy.sh test
```

## 📁 脚本文件说明

### 1. `start_docking_service.sh` - DockingVina服务管理
**功能**: 管理DockingVina API服务的启动、停止、状态查看

**用法**:
```bash
./start_docking_service.sh start      # 启动服务
./start_docking_service.sh stop       # 停止服务
./start_docking_service.sh restart    # 重启服务
./start_docking_service.sh status     # 查看状态
./start_docking_service.sh logs       # 查看日志
```

**特性**:
- ✅ 自动检查conda环境
- ✅ 后台运行，关闭终端不影响服务
- ✅ PID文件管理
- ✅ 完整的日志记录
- ✅ 健康检查

### 2. `setup_autossh.sh` - AutoSSH隧道管理
**功能**: 建立WSL到云服务器的SSH反向隧道

**用法**:
```bash
./setup_autossh.sh start      # 启动隧道
./setup_autossh.sh stop       # 停止隧道
./setup_autossh.sh status     # 查看状态
./setup_autossh.sh test       # 测试连接
./setup_autossh.sh config     # 显示配置
```

**配置参数** (脚本顶部修改):
```bash
CLOUD_SERVER="106.14.212.218"        # 您的云服务器IP地址
CLOUD_USER="your-username"           # 云服务器用户名
SSH_KEY_PATH="$HOME/.ssh/id_rsa"     # SSH私钥路径
LOCAL_DOCKING_PORT=8000
REMOTE_DOCKING_PORT=8000
```

### 3. `nginx_setup.sh` - 云服务器Nginx配置
**功能**: 在云服务器上安装和配置Nginx反向代理

**用法** (在云服务器上运行):
```bash
# 下载脚本到云服务器
scp nginx_setup.sh user@cloud-server:/tmp/

# 在云服务器上执行
sudo /tmp/nginx_setup.sh install     # 安装配置
sudo /tmp/nginx_setup.sh test        # 测试配置
sudo /tmp/nginx_setup.sh uninstall   # 卸载配置
```

**配置参数** (脚本顶部修改):
```bash
DOMAIN="106.14.212.218"              # 您的云服务器IP地址
DOCKING_PORT=8000                     # DockingVina端口
SSL_ENABLED=false                     # 是否启用SSL
EMAIL="your-email@example.com"        # SSL证书邮箱
```

### 4. `deploy.sh` - 一键部署管理
**功能**: 统一管理所有服务，提供完整的部署解决方案

**用法**:
```bash
./deploy.sh start      # 启动所有服务
./deploy.sh stop       # 停止所有服务
./deploy.sh status     # 查看所有状态
./deploy.sh logs       # 查看实时日志
./deploy.sh test       # 测试所有连接
./deploy.sh check      # 环境检查
./deploy.sh config     # 配置助手
```

---

*最后更新: 2025年8月*
