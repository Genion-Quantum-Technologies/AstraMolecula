#!/bin/bash

# AutoSSH反向代理启动脚本
# 用于建立WSL到云服务器的反向隧道

set -e

# 配置变量 - 请根据您的实际情况修改
CLOUD_SERVER="106.14.212.218"       # 云服务器IP地址
CLOUD_USER="root"                    # 云服务器用户名
SSH_KEY_PATH="$HOME/.ssh/pc_wsl2ecs.pem"  # SSH私钥路径

# 隧道配置
LOCAL_DOCKING_PORT=8000              # 本地DockingVina服务端口
REMOTE_DOCKING_PORT=8000            # 远程映射端口

# AutoSSH配置
AUTOSSH_MONITOR_PORT=20000          # AutoSSH监控端口
AUTOSSH_POLL=60                     # 连接检查间隔（秒）
AUTOSSH_GATETIME=30                 # 初始连接等待时间（秒）
AUTOSSH_DEBUG=1                     # 调试模式

# PID文件
PID_FILE="/tmp/autossh_docking.pid"
LOG_FILE="$HOME/logs/autossh_docking.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 创建日志目录
create_log_dir() {
    mkdir -p "$(dirname "$LOG_FILE")"
}

# 检查依赖
check_dependencies() {
    log "检查依赖..."
    
    if ! command -v autossh &> /dev/null; then
        error "autossh未安装，请先安装: sudo apt install autossh"
        exit 1
    fi
    
    if [ ! -f "$SSH_KEY_PATH" ]; then
        error "SSH密钥不存在: $SSH_KEY_PATH"
        echo "请生成SSH密钥对并配置到云服务器:"
        echo "  ssh-keygen -t rsa -b 4096 -C 'your-email@example.com'"
        echo "  ssh-copy-id -i $SSH_KEY_PATH.pub $CLOUD_USER@$CLOUD_SERVER"
        exit 1
    fi
    
    log "依赖检查完成"
}

# 测试SSH连接
test_ssh_connection() {
    log "测试SSH连接到 $CLOUD_USER@$CLOUD_SERVER ..."
    
    if ssh -i "$SSH_KEY_PATH" -o ConnectTimeout=10 -o BatchMode=yes "$CLOUD_USER@$CLOUD_SERVER" "echo 'SSH connection successful'" > /dev/null 2>&1; then
        log "✅ SSH连接测试成功"
    else
        error "❌ SSH连接测试失败"
        echo "请检查:"
        echo "  1. 云服务器IP/域名是否正确: $CLOUD_SERVER"
        echo "  2. 用户名是否正确: $CLOUD_USER"
        echo "  3. SSH密钥是否正确配置: $SSH_KEY_PATH"
        echo "  4. 云服务器SSH服务是否正常运行"
        exit 1
    fi
}

# 检查现有隧道
check_existing_tunnel() {
    if [ -f "$PID_FILE" ]; then
        local old_pid=$(cat "$PID_FILE")
        if ps -p $old_pid > /dev/null 2>&1; then
            warn "发现运行中的AutoSSH隧道 (PID: $old_pid)"
            read -p "是否要停止现有隧道? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_tunnel
            else
                error "隧道已在运行，退出启动"
                exit 1
            fi
        else
            warn "PID文件存在但进程已死，清理PID文件"
            rm -f "$PID_FILE"
        fi
    fi
}

# 启动隧道
start_tunnel() {
    log "启动AutoSSH反向隧道..."
    log "本地端口: $LOCAL_DOCKING_PORT"
    log "远程端口: $REMOTE_DOCKING_PORT"
    log "目标服务器: $CLOUD_USER@$CLOUD_SERVER"
    log "日志文件: $LOG_FILE"
    
    # 设置AutoSSH环境变量
    export AUTOSSH_POLL=$AUTOSSH_POLL
    export AUTOSSH_GATETIME=$AUTOSSH_GATETIME
    export AUTOSSH_DEBUG=$AUTOSSH_DEBUG
    export AUTOSSH_LOGLEVEL=6
    
    # 启动AutoSSH隧道
    autossh \
        -M $AUTOSSH_MONITOR_PORT \
        -f \
        -N \
        -i "$SSH_KEY_PATH" \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o StrictHostKeyChecking=no \
        -R 0.0.0.0:${REMOTE_DOCKING_PORT}:localhost:${LOCAL_DOCKING_PORT} \
        "$CLOUD_USER@$CLOUD_SERVER" \
        > "$LOG_FILE" 2>&1
    
    # 获取AutoSSH进程PID
    sleep 2
    local autossh_pid=$(pgrep -f "autossh.*$AUTOSSH_MONITOR_PORT")
    
    if [ -n "$autossh_pid" ]; then
        echo "$autossh_pid" > "$PID_FILE"
        log "✅ AutoSSH隧道启动成功!"
        log "   PID: $autossh_pid"
        log "   本地端口: $LOCAL_DOCKING_PORT"
        log "   远程端口: $REMOTE_DOCKING_PORT"
        log "   监控端口: $AUTOSSH_MONITOR_PORT"
        log "   日志文件: $LOG_FILE"
        
        # 测试隧道连接
        sleep 5
        test_tunnel_connection
    else
        error "❌ AutoSSH隧道启动失败，请检查日志: $LOG_FILE"
        exit 1
    fi
}

# 测试隧道连接
test_tunnel_connection() {
    log "测试隧道连接..."
    
    # 检查本地服务是否运行
    if ! curl -s -f "http://localhost:$LOCAL_DOCKING_PORT/docs" > /dev/null; then
        warn "本地DockingVina服务未运行，请先启动服务"
        return 1
    fi
    
    # 通过SSH测试远程端口
    if ssh -i "$SSH_KEY_PATH" "$CLOUD_USER@$CLOUD_SERVER" "curl -s -f http://localhost:$REMOTE_DOCKING_PORT/docs" > /dev/null 2>&1; then
        log "✅ 隧道连接测试成功"
    else
        warn "⚠️  隧道连接测试失败，可能需要等待更长时间"
    fi
}

# 停止隧道
stop_tunnel() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "正在停止AutoSSH隧道 (PID: $pid)..."
            kill -TERM $pid
            
            # 等待优雅关闭
            local count=0
            while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # 如果还没停止，强制杀死
            if ps -p $pid > /dev/null 2>&1; then
                warn "优雅关闭超时，强制停止隧道"
                kill -9 $pid
            fi
            
            # 清理相关进程
            pkill -f "ssh.*$CLOUD_USER@$CLOUD_SERVER" 2>/dev/null || true
            
            rm -f "$PID_FILE"
            log "✅ AutoSSH隧道已停止"
        else
            warn "PID文件存在但进程已死"
            rm -f "$PID_FILE"
        fi
    else
        warn "未找到PID文件，隧道可能未运行"
    fi
}

# 查看隧道状态
status_tunnel() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "✅ AutoSSH隧道正在运行"
            echo "   PID: $pid"
            echo "   本地端口: $LOCAL_DOCKING_PORT"
            echo "   远程端口: $REMOTE_DOCKING_PORT"
            echo "   目标服务器: $CLOUD_USER@$CLOUD_SERVER"
            echo "   启动时间: $(ps -o lstart= -p $pid)"
            
            # 检查隧道连接
            if ssh -i "$SSH_KEY_PATH" "$CLOUD_USER@$CLOUD_SERVER" "netstat -ln | grep :$REMOTE_DOCKING_PORT" > /dev/null 2>&1; then
                echo "   隧道状态: ✅ 连接正常"
            else
                echo "   隧道状态: ❌ 连接异常"
            fi
        else
            warn "PID文件存在但进程已死"
            rm -f "$PID_FILE"
            echo "   状态: ❌ 未运行"
        fi
    else
        echo "   状态: ❌ 未运行"
    fi
}

# 查看实时日志
logs_tunnel() {
    if [ -f "$LOG_FILE" ]; then
        log "显示AutoSSH隧道日志 (Ctrl+C退出):"
        tail -f "$LOG_FILE"
    else
        warn "日志文件不存在: $LOG_FILE"
    fi
}

# 重启隧道
restart_tunnel() {
    log "重启AutoSSH隧道..."
    stop_tunnel
    sleep 2
    start_tunnel
}

# 显示配置
show_config() {
    echo "AutoSSH隧道配置:"
    echo "  云服务器: $CLOUD_USER@$CLOUD_SERVER"
    echo "  SSH密钥: $SSH_KEY_PATH"
    echo "  本地端口: $LOCAL_DOCKING_PORT"
    echo "  远程端口: $REMOTE_DOCKING_PORT"
    echo "  监控端口: $AUTOSSH_MONITOR_PORT"
    echo "  日志文件: $LOG_FILE"
    echo ""
    echo "修改配置请编辑脚本顶部的变量"
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            log "启动AutoSSH反向隧道..."
            create_log_dir
            check_dependencies
            test_ssh_connection
            check_existing_tunnel
            start_tunnel
            ;;
        stop)
            log "停止AutoSSH隧道..."
            stop_tunnel
            ;;
        restart)
            restart_tunnel
            ;;
        status)
            status_tunnel
            ;;
        logs)
            logs_tunnel
            ;;
        config)
            show_config
            ;;
        test)
            create_log_dir
            check_dependencies
            test_ssh_connection
            test_tunnel_connection
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs|config|test}"
            echo ""
            echo "命令:"
            echo "  start    启动AutoSSH反向隧道"
            echo "  stop     停止AutoSSH隧道"
            echo "  restart  重启AutoSSH隧道"
            echo "  status   查看隧道状态"
            echo "  logs     查看实时日志"
            echo "  config   显示当前配置"
            echo "  test     测试SSH连接和隧道"
            echo ""
            echo "首次使用前请修改脚本顶部的配置变量"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
