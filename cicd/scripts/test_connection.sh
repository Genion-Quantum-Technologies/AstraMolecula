#!/bin/bash

# 阿里云ECS连接测试脚本
# 用于验证SSH连接和基本环境

set -e

# 配置
CLOUD_SERVER="106.14.212.218"
CLOUD_USER="root"
SSH_KEY="$HOME/.ssh/pc_wsl2ecs.pem"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[OK]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo "=========================================="
echo "  阿里云ECS连接测试"
echo "  服务器: $CLOUD_SERVER"
echo "  用户: $CLOUD_USER"
echo "  密钥: $SSH_KEY"
echo "=========================================="
echo ""

# 1. 检查SSH密钥文件
echo "1. 检查SSH密钥文件..."
if [ -f "$SSH_KEY" ]; then
    log "SSH密钥文件存在"
    
    # 检查权限
    perm=$(stat -c %a "$SSH_KEY")
    if [ "$perm" = "600" ]; then
        log "SSH密钥权限正确 (600)"
    else
        warn "SSH密钥权限不正确，正在修复..."
        chmod 600 "$SSH_KEY"
        log "SSH密钥权限已修复为 600"
    fi
else
    error "SSH密钥文件不存在: $SSH_KEY"
    exit 1
fi

echo ""

# 2. 测试SSH连接
echo "2. 测试SSH连接..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes "$CLOUD_USER@$CLOUD_SERVER" "echo 'SSH连接成功'" 2>/dev/null; then
    log "SSH连接测试成功"
else
    error "SSH连接测试失败"
    echo ""
    echo "可能的原因:"
    echo "1. 阿里云安全组未开放22端口"
    echo "2. ECS实例状态异常"
    echo "3. 密钥不匹配"
    echo ""
    echo "请检查阿里云控制台设置"
    exit 1
fi

echo ""

# 3. 检查服务器基本信息
echo "3. 获取服务器信息..."
server_info=$(ssh -i "$SSH_KEY" "$CLOUD_USER@$CLOUD_SERVER" "
echo '操作系统:' \$(cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"')
echo '内核版本:' \$(uname -r)
echo '系统时间:' \$(date)
echo 'CPU核心:' \$(nproc)
echo '内存信息:' \$(free -h | grep Mem | awk '{print \$2}')
echo '磁盘空间:' \$(df -h / | tail -1 | awk '{print \$4}')
" 2>/dev/null)

if [ $? -eq 0 ]; then
    log "服务器信息获取成功"
    echo "$server_info"
else
    warn "无法获取服务器详细信息"
fi

echo ""

# 4. 检查必要端口
echo "4. 检查网络端口..."
port_check=$(ssh -i "$SSH_KEY" "$CLOUD_USER@$CLOUD_SERVER" "
if command -v netstat >/dev/null 2>&1; then
    echo '端口22 (SSH):' \$(netstat -ln | grep ':22 ' >/dev/null && echo '监听中' || echo '未监听')
    echo '端口80 (HTTP):' \$(netstat -ln | grep ':80 ' >/dev/null && echo '监听中' || echo '未监听')
else
    echo '端口检查工具不可用，跳过端口检查'
fi
" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$port_check"
else
    warn "无法检查端口状态"
fi

echo ""

# 5. 测试网络连通性
echo "5. 测试网络连通性..."
if ping -c 1 "$CLOUD_SERVER" >/dev/null 2>&1; then
    log "服务器网络连通正常"
else
    warn "服务器网络连通性测试失败"
fi

echo ""
echo "=========================================="
echo "           测试完成"
echo "=========================================="
echo ""

# 显示配置状态
if ssh -i "$SSH_KEY" "$CLOUD_USER@$CLOUD_SERVER" "echo 'test'" >/dev/null 2>&1; then
    log "✅ 阿里云ECS连接配置正确"
    echo ""
    echo "您可以继续执行以下步骤:"
    echo "1. 运行环境检查: ./deploy.sh check"
    echo "2. 启动WSL服务: ./deploy.sh start"
    echo "3. 配置云服务器Nginx:"
    echo "   scp -i ~/.ssh/pc_wsl2ecs.pem nginx_setup.sh root@106.14.212.218:/tmp/"
    echo "   ssh -i ~/.ssh/pc_wsl2ecs.pem root@106.14.212.218 'sudo /tmp/nginx_setup.sh install'"
else
    error "❌ 连接配置存在问题"
    echo ""
    echo "请检查:"
    echo "1. 阿里云控制台安全组配置"
    echo "2. ECS实例状态"
    echo "3. SSH密钥配置"
fi

echo ""
