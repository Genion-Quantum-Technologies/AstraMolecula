#!/bin/bash
# ============================================================
# AstraMolecula Docker 快速启动脚本
# 直接使用 docker run 启动容器（无需 docker-compose）
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# ============================================================
# 配置变量 - 根据实际环境修改
# ============================================================
CONTAINER_NAME="astramolecula"
IMAGE_NAME="astramolecula:latest"
HOST_PORT=8001
CONTAINER_PORT=8000

# 数据库配置 (连接宿主机上的 PostgreSQL)
DB_HOST="172.17.0.1"
DB_PORT="5432"
DB_USER="admin"
DB_PASSWORD="secret"
DB_NAME="mydatabase"

# SeaweedFS 配置 (连接宿主机上的 SeaweedFS)
SEAWEED_FILER_ENDPOINT="http://172.17.0.1:8888"

# 前端 URL
FRONTEND_BASE_URL="https://api.genionaitech.com"

# ============================================================
# 函数定义
# ============================================================

show_help() {
    echo "AstraMolecula Docker 快速启动脚本"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start       启动容器"
    echo "  stop        停止容器"
    echo "  restart     重启容器"
    echo "  status      查看容器状态"
    echo "  logs        查看容器日志"
    echo "  shell       进入容器 shell"
    echo "  build       构建 Docker 镜像"
    echo "  clean       清理容器和镜像"
    echo ""
    echo "Options:"
    echo "  -d, --detach    后台运行 (默认)"
    echo "  -f, --follow    跟随日志输出"
    echo "  --rebuild       启动前重新构建镜像"
    echo ""
    echo "Examples:"
    echo "  $0 start              # 启动容器"
    echo "  $0 start --rebuild    # 重建镜像并启动"
    echo "  $0 logs -f            # 实时查看日志"
    echo "  $0 shell              # 进入容器"
}

# 检查容器是否在运行
is_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# 检查容器是否存在
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# 构建镜像
build_image() {
    log_info "构建 Docker 镜像..."
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
    DOCKER_DIR="$SCRIPT_DIR/../docker"
    
    cd "$PROJECT_ROOT"
    docker build -t "$IMAGE_NAME" -f cicd/docker/Dockerfile .
    
    log_info "✅ 镜像构建完成: $IMAGE_NAME"
}

# 启动容器
start_container() {
    local rebuild=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rebuild)
                rebuild=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    if is_running; then
        log_warn "容器 $CONTAINER_NAME 已在运行"
        show_status
        return 0
    fi
    
    # 如果容器存在但未运行，先删除
    if container_exists; then
        log_info "删除已停止的容器..."
        docker rm "$CONTAINER_NAME"
    fi
    
    # 如果需要重建镜像
    if [ "$rebuild" = true ]; then
        build_image
    fi
    
    log_info "启动容器 $CONTAINER_NAME..."
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "${HOST_PORT}:${CONTAINER_PORT}" \
        -e "ASTRA_DATABASE_HOST=${DB_HOST}" \
        -e "ASTRA_DATABASE_PORT=${DB_PORT}" \
        -e "ASTRA_DATABASE_USER=${DB_USER}" \
        -e "ASTRA_DATABASE_PASSWORD=${DB_PASSWORD}" \
        -e "ASTRA_DATABASE_DATABASE=${DB_NAME}" \
        -e "SEAWEED_FILER_ENDPOINT=${SEAWEED_FILER_ENDPOINT}" \
        -e "FRONTEND_BASE_URL=${FRONTEND_BASE_URL}" \
        --restart unless-stopped \
        "$IMAGE_NAME"
    
    log_info "等待服务启动..."
    sleep 5
    
    # 检查健康状态
    check_health
}

# 停止容器
stop_container() {
    if is_running; then
        log_info "停止容器 $CONTAINER_NAME..."
        docker stop "$CONTAINER_NAME"
        log_info "✅ 容器已停止"
    else
        log_warn "容器 $CONTAINER_NAME 未在运行"
    fi
}

# 重启容器
restart_container() {
    log_info "重启容器 $CONTAINER_NAME..."
    stop_container
    
    # 删除旧容器
    if container_exists; then
        docker rm "$CONTAINER_NAME"
    fi
    
    start_container "$@"
}

# 查看状态
show_status() {
    echo ""
    log_info "容器状态:"
    echo "-------------------------------------------"
    
    if is_running; then
        docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.ID}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        echo "环境变量:"
        docker exec "$CONTAINER_NAME" env | grep -E "^(ASTRA_|SEAWEED_|FRONTEND_)" | sort
    else
        log_warn "容器 $CONTAINER_NAME 未在运行"
        
        if container_exists; then
            echo "容器存在但已停止:"
            docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.ID}}\t{{.Status}}"
        fi
    fi
    echo "-------------------------------------------"
}

# 查看日志
view_logs() {
    if ! container_exists; then
        log_error "容器 $CONTAINER_NAME 不存在"
        exit 1
    fi
    
    docker logs "$@" "$CONTAINER_NAME"
}

# 进入容器 shell
enter_shell() {
    if ! is_running; then
        log_error "容器 $CONTAINER_NAME 未在运行"
        exit 1
    fi
    
    log_info "进入容器 shell..."
    docker exec -it "$CONTAINER_NAME" /bin/bash
}

# 健康检查
check_health() {
    log_info "检查服务健康状态..."
    
    local max_attempts=30
    local attempt=1
    local url="http://localhost:${HOST_PORT}/health"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log_info "✅ 服务健康!"
            echo ""
            echo "健康检查响应:"
            curl -s "$url" | python3 -m json.tool 2>/dev/null || curl -s "$url"
            echo ""
            echo "-------------------------------------------"
            echo "服务地址: http://localhost:${HOST_PORT}"
            echo "API 文档: http://localhost:${HOST_PORT}/docs"
            echo "-------------------------------------------"
            return 0
        fi
        
        echo -ne "\r${YELLOW}[等待]${NC} 服务启动中... (尝试 $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    echo ""
    log_error "❌ 服务健康检查失败"
    log_info "查看日志: $0 logs -f"
    return 1
}

# 清理
clean_up() {
    log_warn "这将删除容器 $CONTAINER_NAME"
    read -p "确定要继续吗? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 停止容器
        if is_running; then
            docker stop "$CONTAINER_NAME"
        fi
        
        # 删除容器
        if container_exists; then
            docker rm "$CONTAINER_NAME"
            log_info "✅ 容器已删除"
        fi
        
        # 询问是否删除镜像
        read -p "是否同时删除镜像 $IMAGE_NAME? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker rmi "$IMAGE_NAME" 2>/dev/null || log_warn "镜像删除失败或不存在"
            log_info "✅ 镜像已删除"
        fi
    else
        log_info "取消操作"
    fi
}

# ============================================================
# 主函数
# ============================================================
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    local command=$1
    shift
    
    case $command in
        start)
            start_container "$@"
            ;;
        stop)
            stop_container
            ;;
        restart)
            restart_container "$@"
            ;;
        status)
            show_status
            ;;
        logs)
            view_logs "$@"
            ;;
        shell)
            enter_shell
            ;;
        build)
            build_image
            ;;
        clean)
            clean_up
            ;;
        health)
            check_health
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
