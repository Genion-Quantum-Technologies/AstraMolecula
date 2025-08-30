#!/bin/bash

# 阿里云ECS服务器一键配置脚本
# 适用于阿里云服务器的DockingVina服务部署

set -e

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo "================================================"
echo "    阿里云ECS DockingVina服务一键配置"
echo "================================================"
echo ""
echo "配置信息:"
echo "  云服务器IP: 106.14.212.218"
echo "  用户名: root"
echo "  SSL: 禁用 (使用HTTP)"
echo "  服务端口: 8000"
echo ""

# 检查SSH密钥
check_ssh_key() {
    local ssh_key="$HOME/.ssh/pc_wsl2ecs.pem"
    
    if [ ! -f "$ssh_key" ]; then
        warn "阿里云SSH密钥不存在: $ssh_key"
        echo ""
        info "请确保您的阿里云ECS密钥文件存在于: $ssh_key"
        echo "如果您使用的是其他密钥文件，请:"
        echo "1. 将密钥文件复制到 $ssh_key"
        echo "2. 或者编辑脚本修改 SSH_KEY_PATH 变量"
        return 1
    else
        # 检查密钥文件权限
        chmod 600 "$ssh_key"
        log "✅ 阿里云SSH密钥已存在: $ssh_key"
    fi
    
    return 0
}

# 配置SSH密钥到阿里云服务器
setup_ssh_key() {
    local ssh_key="$HOME/.ssh/pc_wsl2ecs.pem"
    
    log "测试阿里云ECS SSH连接..."
    
    if ssh -i "$ssh_key" -o ConnectTimeout=10 -o BatchMode=yes root@106.14.212.218 "echo 'SSH连接成功'" 2>/dev/null; then
        log "✅ SSH连接已配置且正常工作"
        return 0
    else
        warn "SSH连接测试失败"
        echo ""
        info "可能的原因:"
        echo "1. 阿里云安全组未开放22端口"
        echo "2. ECS实例未正确配置此密钥"
        echo "3. 密钥文件权限不正确"
        echo ""
        echo "解决方案:"
        echo "1. 检查阿里云控制台安全组规则"
        echo "2. 确认ECS实例绑定了正确的密钥对"
        echo "3. 检查密钥文件权限: chmod 600 $ssh_key"
        return 1
    fi
}

# 应用配置
apply_configuration() {

# 测试SSH连接
test_ssh_connection() {
    log "测试SSH连接..."
    
    if ssh -i "$HOME/.ssh/pc_wsl2ecs.pem" -o ConnectTimeout=10 -o BatchMode=yes root@106.14.212.218 "echo 'SSH连接成功'" 2>/dev/null; then
        log "✅ SSH连接测试成功"
        return 0
    else
        error "❌ SSH连接测试失败"
        echo ""
        echo "可能的原因:"
        echo "1. 阿里云安全组未开放22端口"
        echo "2. ECS实例状态异常"
        echo "3. 密钥文件不匹配或权限问题"
        echo ""
        echo "解决方案:"
        echo "1. 检查阿里云安全组规则，确保开放22端口"
        echo "2. 确认ECS实例正常运行"
        echo "3. 验证密钥文件: ls -la ~/.ssh/pc_wsl2ecs.pem"
        echo "4. 检查密钥权限: chmod 600 ~/.ssh/pc_wsl2ecs.pem"
        return 1
    fi
}

# 检查阿里云安全组配置
check_aliyun_security_group() {
    echo ""
    info "阿里云安全组配置检查清单:"
    echo "请确保以下端口在安全组中已开放:"
    echo ""
    echo "  ✓ 22/TCP   - SSH连接"
    echo "  ✓ 80/TCP   - HTTP服务"
    echo "  ✓ 443/TCP  - HTTPS服务 (可选)"
    echo ""
    echo "配置步骤:"
    echo "1. 登录阿里云控制台"
    echo "2. 进入 '云服务器ECS' -> '实例与镜像' -> '实例'"
    echo "3. 找到您的实例，点击 '管理'"
    echo "4. 在左侧菜单选择 '安全组'"
    echo "5. 点击安全组ID进入配置"
    echo "6. 添加以上端口的入方向规则"
    echo ""
    read -p "确认安全组已正确配置后按回车继续..."
}

# 应用配置
apply_configuration() {
    log "应用DockingVina配置..."
    
    # 修改setup_autossh.sh中的配置
    sed -i 's/CLOUD_SERVER=".*"/CLOUD_SERVER="106.14.212.218"/' "$SCRIPT_DIR/setup_autossh.sh"
    sed -i 's/CLOUD_USER=".*"/CLOUD_USER="root"/' "$SCRIPT_DIR/setup_autossh.sh"
    sed -i "s|SSH_KEY_PATH=\".*\"|SSH_KEY_PATH=\"$HOME/.ssh/pc_wsl2ecs.pem\"|" "$SCRIPT_DIR/setup_autossh.sh"
    
    log "✅ 配置已应用到 setup_autossh.sh"
}

# 显示下一步操作
show_next_steps() {
    echo ""
    echo "================================================"
    echo "              配置完成！"
    echo "================================================"
    echo ""
    echo "接下来的部署步骤:"
    echo ""
    echo "1. 检查环境和启动WSL服务:"
    echo "   $SCRIPT_DIR/deploy.sh check"
    echo "   $SCRIPT_DIR/deploy.sh start"
    echo ""
    echo "2. 在阿里云服务器上配置Nginx:"
    echo "   scp -i ~/.ssh/pc_wsl2ecs.pem $SCRIPT_DIR/nginx_setup.sh root@106.14.212.218:/tmp/"
    echo "   ssh -i ~/.ssh/pc_wsl2ecs.pem root@106.14.212.218 'sudo /tmp/nginx_setup.sh install'"
    echo ""
    echo "3. 验证部署:"
    echo "   curl http://106.14.212.218/docs"
    echo ""
    echo "服务访问地址:"
    echo "  🌐 API文档: http://106.14.212.218/docs"
    echo "  💓 健康检查: http://106.14.212.218/health"
    echo "  📡 完整API: http://106.14.212.218/"
    echo ""
    echo "================================================"
}

# 主函数
main() {
    case "${1:-auto}" in
        auto)
            log "开始阿里云ECS自动配置..."
            check_ssh_key
            if [ $? -eq 0 ]; then
                check_aliyun_security_group
                setup_ssh_key
                if [ $? -eq 0 ]; then
                    apply_configuration
                    show_next_steps
                else
                    error "SSH连接配置失败，请检查阿里云安全组和ECS设置"
                    exit 1
                fi
            else
                error "SSH密钥检查失败，请确保密钥文件存在"
                exit 1
            fi
            ;;
        ssh-only)
            log "仅测试SSH连接..."
            check_ssh_key
            setup_ssh_key
            ;;
        test)
            log "测试SSH连接..."
            test_ssh_connection
            ;;
        *)
            echo "用法: $0 [auto|ssh-only|test]"
            echo ""
            echo "命令:"
            echo "  auto      完整自动配置 (默认)"
            echo "  ssh-only  仅测试SSH连接"
            echo "  test      测试SSH连接"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
