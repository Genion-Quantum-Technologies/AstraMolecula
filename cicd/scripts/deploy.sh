#!/bin/bash

# DockingVina一键部署脚本
# 统一管理所有服务的启动、停止和状态检查

set -e

# 项目路径
PROJECT_DIR="/home/davis/projects/AstraMolecula/dockingVina"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 检查脚本是否存在
check_scripts() {
    local missing_scripts=()
    
    if [ ! -f "$SCRIPT_DIR/start_docking_service.sh" ]; then
        missing_scripts+=("start_docking_service.sh")
    fi
    
    if [ ! -f "$SCRIPT_DIR/setup_autossh.sh" ]; then
        missing_scripts+=("setup_autossh.sh")
    fi
    
    if [ ${#missing_scripts[@]} -ne 0 ]; then
        error "缺少必要的脚本文件:"
        for script in "${missing_scripts[@]}"; do
            echo "  - $script"
        done
        exit 1
    fi
}

# 启动所有服务
start_all() {
    log "🚀 启动DockingVina完整服务..."
    
    # 1. 启动DockingVina服务
    log "1. 启动DockingVina API服务..."
    "$SCRIPT_DIR/start_docking_service.sh" start
    
    # 等待服务启动
    sleep 5
    
    # 2. 启动AutoSSH隧道
    log "2. 启动AutoSSH反向隧道..."
    "$SCRIPT_DIR/setup_autossh.sh" start
    
    # 等待隧道建立
    sleep 3
    
    log "✅ 所有服务启动完成!"
    echo ""
    status_all
}

# 停止所有服务
stop_all() {
    log "🛑 停止DockingVina所有服务..."
    
    # 1. 停止AutoSSH隧道
    log "1. 停止AutoSSH隧道..."
    "$SCRIPT_DIR/setup_autossh.sh" stop
    
    # 2. 停止DockingVina服务
    log "2. 停止DockingVina API服务..."
    "$SCRIPT_DIR/start_docking_service.sh" stop
    
    log "✅ 所有服务已停止"
}

# 重启所有服务
restart_all() {
    log "🔄 重启DockingVina所有服务..."
    stop_all
    sleep 3
    start_all
}

# 查看所有服务状态
status_all() {
    echo ""
    echo "======================================"
    echo "     DockingVina服务状态总览"
    echo "======================================"
    
    # DockingVina服务状态
    echo ""
    info "📡 DockingVina API服务:"
    "$SCRIPT_DIR/start_docking_service.sh" status
    
    # AutoSSH隧道状态
    echo ""
    info "🔄 AutoSSH反向隧道:"
    "$SCRIPT_DIR/setup_autossh.sh" status
    
    # 端口检查
    echo ""
    info "🔌 端口占用情况:"
    echo "   端口 8000 (DockingVina):"
    if lsof -Pi :8000 -sTCP:LISTEN >/dev/null 2>&1; then
        echo "     ✅ 正在监听"
    else
        echo "     ❌ 未监听"
    fi
    
    # 网络连接测试
    echo ""
    info "🌐 服务连接测试:"
    
    # 测试本地API
    if curl -s -f "http://localhost:8000/docs" >/dev/null 2>&1; then
        echo "   本地API (8000):     ✅ 连接正常"
    else
        echo "   本地API (8000):     ❌ 连接失败"
    fi
    
    echo ""
    echo "======================================"
}

# 查看实时日志
logs_all() {
    echo "选择要查看的日志:"
    echo "1) DockingVina服务日志"
    echo "2) AutoSSH隧道日志"
    echo "3) 同时查看所有日志"
    read -p "请选择 (1-3): " choice
    
    case $choice in
        1)
            "$SCRIPT_DIR/start_docking_service.sh" logs
            ;;
        2)
            "$SCRIPT_DIR/setup_autossh.sh" logs
            ;;
        3)
            log "同时显示所有日志 (Ctrl+C退出):"
            # 使用tmux或screen同时显示多个日志，如果没有则依次显示
            if command -v tmux >/dev/null 2>&1; then
                tmux new-session -d -s logs
                tmux split-window -h
                tmux send-keys -t 0 "tail -f $PROJECT_DIR/logs/docking_service.log" Enter
                tmux send-keys -t 1 "tail -f $HOME/logs/autossh_docking.log" Enter
                tmux attach-session -t logs
            else
                warn "建议安装tmux以同时查看多个日志: sudo apt install tmux"
                echo "当前显示DockingVina日志，按Ctrl+C可切换到AutoSSH日志"
                "$SCRIPT_DIR/start_docking_service.sh" logs
            fi
            ;;
        *)
            error "无效选择"
            exit 1
            ;;
    esac
}

# 测试服务连接
test_all() {
    log "🧪 测试DockingVina服务连接..."
    
    echo ""
    info "1. 测试本地DockingVina服务..."
    if curl -s -f "http://localhost:8000/docs" >/dev/null 2>&1; then
        log "✅ 本地DockingVina服务响应正常"
    else
        error "❌ 本地DockingVina服务无响应"
        echo "   请检查服务是否启动: $SCRIPT_DIR/start_docking_service.sh status"
        return 1
    fi
    
    echo ""
    info "2. 测试AutoSSH隧道连接..."
    "$SCRIPT_DIR/setup_autossh.sh" test
    
    echo ""
    info "3. 测试API端点..."
    
    # 测试健康检查
    if curl -s "http://localhost:8000/health" 2>/dev/null | grep -q "healthy"; then
        log "✅ 健康检查端点正常"
    else
        warn "⚠️  健康检查端点异常"
    fi
    
    # 测试API文档
    if curl -s -I "http://localhost:8000/docs" 2>/dev/null | grep -q "200 OK"; then
        log "✅ API文档端点正常"
    else
        warn "⚠️  API文档端点异常"
    fi
    
    echo ""
    log "✅ 服务测试完成"
}

# 环境检查
check_environment() {
    log "🔍 检查部署环境..."
    
    echo ""
    info "检查依赖工具:"
    
    # 检查conda
    if command -v conda >/dev/null 2>&1; then
        echo "   conda:          ✅ 已安装"
    else
        echo "   conda:          ❌ 未安装"
        warn "请先安装Anaconda或Miniconda"
    fi
    
    # 检查autossh
    if command -v autossh >/dev/null 2>&1; then
        echo "   autossh:        ✅ 已安装"
    else
        echo "   autossh:        ❌ 未安装"
        warn "请安装autossh: sudo apt install autossh"
    fi
    
    # 检查curl
    if command -v curl >/dev/null 2>&1; then
        echo "   curl:           ✅ 已安装"
    else
        echo "   curl:           ❌ 未安装"
        warn "请安装curl: sudo apt install curl"
    fi
    
    echo ""
    info "检查conda环境:"
    if conda env list | grep -q "dockingvina_final"; then
        echo "   dockingvina_final环境:      ✅ 已创建"
    else
        echo "   dockingvina_final环境:      ❌ 未创建"
        warn "请创建conda环境: conda env create -f env.yml"
    fi
    
    echo ""
    info "检查项目文件:"
    
    local required_files=(
        "main.py"
        "env.yml"
        "start_docking_service.sh"
        "setup_autossh.sh"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            echo "   $file: ✅ 存在"
        else
            echo "   $file: ❌ 缺失"
        fi
    done
    
    echo ""
    info "检查目录结构:"
    
    local required_dirs=(
        "logs"
        "uploads"
        "database"
        "jobs/docking"
        "jobs/generate"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            echo "   $dir/: ✅ 存在"
        else
            echo "   $dir/: ⚠️  将自动创建"
        fi
    done
    
    echo ""
    log "✅ 环境检查完成"
}

# 配置助手
configure() {
    log "📝 DockingVina服务配置助手"
    
    echo ""
    echo "请按照提示配置AutoSSH连接参数:"
    echo ""
    
    read -p "云服务器IP或域名: " cloud_server
    read -p "云服务器用户名: " cloud_user
    read -p "SSH密钥路径 (默认: ~/.ssh/id_rsa): " ssh_key
    ssh_key=${ssh_key:-"$HOME/.ssh/id_rsa"}
    
    echo ""
    echo "生成的配置:"
    echo "  云服务器: $cloud_user@$cloud_server"
    echo "  SSH密钥: $ssh_key"
    echo "  本地端口: 8000"
    echo "  远程端口: 8000"
    
    read -p "是否应用此配置? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 修改setup_autossh.sh中的配置
        sed -i "s/CLOUD_SERVER=\".*\"/CLOUD_SERVER=\"$cloud_server\"/" setup_autossh.sh
        sed -i "s/CLOUD_USER=\".*\"/CLOUD_USER=\"$cloud_user\"/" setup_autossh.sh
        sed -i "s|SSH_KEY_PATH=\".*\"|SSH_KEY_PATH=\"$ssh_key\"|" setup_autossh.sh
        
        log "✅ 配置已应用到 setup_autossh.sh"
        
        # 测试SSH连接
        echo ""
        read -p "是否测试SSH连接? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            "$SCRIPT_DIR/setup_autossh.sh" test
        fi
    else
        info "配置未应用，请手动编辑 setup_autossh.sh"
    fi
}

# 显示使用说明
show_help() {
    echo "DockingVina服务部署脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start      启动所有服务 (DockingVina + AutoSSH)"
    echo "  stop       停止所有服务"
    echo "  restart    重启所有服务"
    echo "  status     查看服务状态"
    echo "  logs       查看实时日志"
    echo "  test       测试服务连接"
    echo "  check      检查部署环境"
    echo "  config     配置助手"
    echo "  help       显示此帮助信息"
    echo ""
    echo "单独控制:"
    echo "  $SCRIPT_DIR/start_docking_service.sh {start|stop|restart|status|logs}"
    echo "  $SCRIPT_DIR/setup_autossh.sh {start|stop|restart|status|logs|test}"
    echo ""
    echo "部署流程:"
    echo "  1. 运行环境检查: $0 check"
    echo "  2. 配置连接参数: $0 config"
    echo "  3. 启动服务: $0 start"
    echo "  4. 查看状态: $0 status"
    echo "  5. 测试连接: $0 test"
    echo ""
    echo "日志文件:"
    echo "  DockingVina: logs/docking_service.log"
    echo "  AutoSSH: ~/logs/autossh_docking.log"
}

# 主函数
main() {
    # 检查必要的脚本
    check_scripts
    
    case "${1:-help}" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            restart_all
            ;;
        status)
            status_all
            ;;
        logs)
            logs_all
            ;;
        test)
            test_all
            ;;
        check)
            check_environment
            ;;
        config)
            configure
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
