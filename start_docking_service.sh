#!/bin/bash

# DockingVina服务启动脚本
# 用于在WSL中启动DockingVina服务并保持后台运行

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_DIR="/home/davis/projects/AstraMolecula/dockingVina"
CONDA_ENV_NAME="dockingvina_final"
SERVICE_PORT=8000
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$LOG_DIR/docking_service.pid"
LOG_FILE="$LOG_DIR/docking_service.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 创建必要的目录
create_directories() {
    log "创建必要的目录..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$PROJECT_DIR/uploads"
    mkdir -p "$PROJECT_DIR/jobs/docking"
    mkdir -p "$PROJECT_DIR/jobs/generate"
    mkdir -p "$PROJECT_DIR/database"
}

# 检查conda环境
check_conda_env() {
    log "检查conda环境: $CONDA_ENV_NAME"
    
    if ! conda env list | grep -q "$CONDA_ENV_NAME"; then
        warn "conda环境 $CONDA_ENV_NAME 不存在，正在创建..."
        cd "$PROJECT_DIR"
        conda env create -f env.yml
        log "conda环境创建完成"
    else
        log "conda环境 $CONDA_ENV_NAME 已存在"
    fi
}

# 检查端口占用
check_port() {
    if lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        warn "端口 $SERVICE_PORT 已被占用"
        local pid=$(lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t)
        echo "占用端口的进程 PID: $pid"
        read -p "是否要杀死该进程? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $pid
            log "已杀死进程 $pid"
        else
            error "端口被占用，无法启动服务"
            exit 1
        fi
    fi
}

# 检查现有服务
check_existing_service() {
    if [ -f "$PID_FILE" ]; then
        local old_pid=$(cat "$PID_FILE")
        if ps -p $old_pid > /dev/null 2>&1; then
            warn "发现运行中的DockingVina服务 (PID: $old_pid)"
            read -p "是否要停止现有服务? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_service
            else
                error "服务已在运行，退出启动"
                exit 1
            fi
        else
            warn "PID文件存在但进程已死，清理PID文件"
            rm -f "$PID_FILE"
        fi
    fi
}

# 启动服务
start_service() {
    log "切换到项目目录: $PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    log "激活conda环境: $CONDA_ENV_NAME"
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate "$CONDA_ENV_NAME"
    
    log "检查Python包依赖..."
    python -c "import fastapi, uvicorn, rdkit; print('所有依赖包可用')" || {
        error "Python包依赖检查失败"
        exit 1
    }
    
    log "启动DockingVina服务..."
    log "端口: $SERVICE_PORT"
    log "日志文件: $LOG_FILE"
    log "PID文件: $PID_FILE"
    
    # 使用nohup启动服务并保存PID
    nohup uvicorn main:app \
        --host 0.0.0.0 \
        --port $SERVICE_PORT \
        --workers 1 \
        --access-log \
        --log-level info \
        > "$LOG_FILE" 2>&1 &
    
    local service_pid=$!
    echo $service_pid > "$PID_FILE"
    
    # 等待服务启动
    log "等待服务启动..."
    sleep 5
    
    # 检查服务是否成功启动
    if ps -p $service_pid > /dev/null 2>&1; then
        log "✅ DockingVina服务启动成功!"
        log "   PID: $service_pid"
        log "   端口: $SERVICE_PORT"
        log "   访问地址: http://localhost:$SERVICE_PORT"
        log "   API文档: http://localhost:$SERVICE_PORT/docs"
        log "   日志文件: $LOG_FILE"
        
        # 测试API连接
        sleep 2
        if curl -s -f "http://localhost:$SERVICE_PORT/docs" > /dev/null; then
            log "✅ API服务响应正常"
        else
            warn "⚠️  API服务可能未完全启动，请检查日志"
        fi
    else
        error "❌ 服务启动失败，请检查日志: $LOG_FILE"
        exit 1
    fi
}

# 停止服务
stop_service() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "正在停止DockingVina服务 (PID: $pid)..."
            kill -TERM $pid
            
            # 等待优雅关闭
            local count=0
            while ps -p $pid > /dev/null 2>&1 && [ $count -lt 30 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # 如果还没停止，强制杀死
            if ps -p $pid > /dev/null 2>&1; then
                warn "优雅关闭超时，强制停止服务"
                kill -9 $pid
            fi
            
            rm -f "$PID_FILE"
            log "✅ 服务已停止"
        else
            warn "PID文件存在但进程已死"
            rm -f "$PID_FILE"
        fi
    else
        warn "未找到PID文件，服务可能未运行"
    fi
}

# 查看服务状态
status_service() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "✅ DockingVina服务正在运行"
            echo "   PID: $pid"
            echo "   端口: $SERVICE_PORT"
            echo "   启动时间: $(ps -o lstart= -p $pid)"
            echo "   内存使用: $(ps -o rss= -p $pid | awk '{print $1/1024 " MB"}')"
            
            # 检查API响应
            if curl -s -f "http://localhost:$SERVICE_PORT/docs" > /dev/null; then
                echo "   API状态: ✅ 正常响应"
            else
                echo "   API状态: ❌ 无响应"
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
logs_service() {
    if [ -f "$LOG_FILE" ]; then
        log "显示DockingVina服务日志 (Ctrl+C退出):"
        tail -f "$LOG_FILE"
    else
        warn "日志文件不存在: $LOG_FILE"
    fi
}

# 重启服务
restart_service() {
    log "重启DockingVina服务..."
    stop_service
    sleep 2
    start_service
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            log "启动DockingVina服务..."
            create_directories
            check_conda_env
            check_existing_service
            check_port
            start_service
            ;;
        stop)
            log "停止DockingVina服务..."
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            status_service
            ;;
        logs)
            logs_service
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs}"
            echo ""
            echo "命令:"
            echo "  start    启动DockingVina服务"
            echo "  stop     停止DockingVina服务"
            echo "  restart  重启DockingVina服务"
            echo "  status   查看服务状态"
            echo "  logs     查看实时日志"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
