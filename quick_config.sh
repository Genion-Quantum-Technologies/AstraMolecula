#!/bin/bash

# 快速配置脚本 - 设置云服务器用户名
# 用于快速配置AutoSSH连接参数

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo "=========================================="
echo "    DockingVina服务快速配置工具"
echo "    (适用于阿里云服务器)"
echo "=========================================="
echo ""
echo "云服务器IP: 106.14.212.218 (已配置)"
echo "默认用户名: root (阿里云ECS默认)"
echo ""

# 获取用户名
read -p "请输入云服务器用户名 [默认: root]: " cloud_user
cloud_user=${cloud_user:-"root"}

if [ -z "$cloud_user" ]; then
    cloud_user="root"
fi

# 获取SSH密钥路径
echo ""
echo "SSH密钥路径选项:"
echo "1) 使用您的阿里云密钥: ~/.ssh/pc_wsl2ecs.pem (推荐)"
echo "2) 使用默认路径: ~/.ssh/id_rsa"
echo "3) 自定义路径"
read -p "请选择 (1-3): " key_choice

case $key_choice in
    1)
        ssh_key="$HOME/.ssh/pc_wsl2ecs.pem"
        ;;
    2)
        ssh_key="$HOME/.ssh/id_rsa"
        ;;
    3)
        read -p "请输入SSH密钥完整路径: " ssh_key
        if [ ! -f "$ssh_key" ]; then
            echo "❌ SSH密钥文件不存在: $ssh_key"
            exit 1
        fi
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "配置预览:"
echo "  云服务器: $cloud_user@106.14.212.218"
echo "  SSH密钥: $ssh_key"
echo "  本地端口: 8000"
echo "  远程端口: 8000"
echo ""

read -p "确认应用此配置? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "应用配置到 setup_autossh.sh..."
    
    # 修改setup_autossh.sh中的配置
    sed -i "s/CLOUD_USER=\".*\"/CLOUD_USER=\"$cloud_user\"/" setup_autossh.sh
    sed -i "s|SSH_KEY_PATH=\".*\"|SSH_KEY_PATH=\"$ssh_key\"|" setup_autossh.sh
    
    log "✅ 配置已成功应用!"
    
    echo ""
    info "接下来的步骤:"
    echo "1. 确保SSH密钥已配置到云服务器:"
    echo "   ssh-copy-id -i $ssh_key.pub $cloud_user@106.14.212.218"
    echo ""
    echo "2. 测试SSH连接:"
    echo "   ./setup_autossh.sh test"
    echo ""
    echo "3. 启动所有服务:"
    echo "   ./deploy.sh start"
    echo ""
    echo "4. 在云服务器上配置Nginx:"
    echo "   scp nginx_setup.sh $cloud_user@106.14.212.218:/tmp/"
    echo "   ssh $cloud_user@106.14.212.218 'sudo /tmp/nginx_setup.sh install'"
    echo ""
    echo "部署完成后，您可以通过以下地址访问:"
    echo "  API文档: http://106.14.212.218/docs"
    echo "  健康检查: http://106.14.212.218/health"
    
else
    echo "配置未应用"
fi
