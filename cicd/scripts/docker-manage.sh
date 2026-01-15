#!/bin/bash
# ============================================================
# AstraMolecula Docker 管理脚本
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 显示帮助
show_help() {
    echo "AstraMolecula Docker 管理脚本"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build       构建 Docker 镜像"
    echo "  start       启动服务 (使用完整配置，包含 PostgreSQL)"
    echo "  start-dev   启动开发环境 (仅应用，连接本地数据库)"
    echo "  stop        停止服务"
    echo "  logs        查看日志"
    echo "  shell       进入容器 shell"
    echo "  clean       清理容器和镜像"
    echo "  test        测试服务健康状态"
    echo ""
    echo "Options:"
    echo "  --storage   包含 SeaweedFS 存储服务 (仅 start 命令)"
    echo "  --rebuild   重新构建镜像"
    echo ""
    echo "Examples:"
    echo "  $0 build                # 构建镜像"
    echo "  $0 start                # 启动服务(应用+PostgreSQL)"
    echo "  $0 start --storage      # 启动服务(包含SeaweedFS)"
    echo "  $0 start-dev            # 启动开发环境"
    echo "  $0 logs -f              # 实时查看日志"
}

# 构建镜像
build_image() {
    log_info "Building AstraMolecula Docker image..."
    cd "$DOCKER_DIR"
    docker compose build
    log_info "Build completed!"
}

# 启动完整服务
start_services() {
    local profile=""
    local rebuild=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --storage)
                profile="--profile storage"
                shift
                ;;
            --rebuild)
                rebuild="--build"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log_info "Starting AstraMolecula services..."
    cd "$DOCKER_DIR"
    docker compose $profile up -d $rebuild
    
    log_info "Waiting for services to be ready..."
    sleep 5
    
    # 检查健康状态
    test_health
}

# 启动开发环境
start_dev() {
    local rebuild=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rebuild)
                rebuild="--build"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log_info "Starting AstraMolecula development environment..."
    cd "$DOCKER_DIR"
    docker compose -f docker-compose.dev.yml up -d $rebuild
    
    log_info "Waiting for service to be ready..."
    sleep 10
    
    # 检查健康状态
    test_health
}

# 停止服务
stop_services() {
    log_info "Stopping AstraMolecula services..."
    cd "$DOCKER_DIR"
    docker compose down 2>/dev/null || true
    docker compose -f docker-compose.dev.yml down 2>/dev/null || true
    log_info "Services stopped!"
}

# 查看日志
view_logs() {
    cd "$DOCKER_DIR"
    if docker compose ps -q 2>/dev/null | grep -q .; then
        docker compose logs "$@"
    elif docker compose -f docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
        docker compose -f docker-compose.dev.yml logs "$@"
    else
        log_error "No running containers found"
        exit 1
    fi
}

# 进入容器 shell
enter_shell() {
    local container_name="astramolecula-app"
    
    # 检查开发容器
    if docker ps --format '{{.Names}}' | grep -q "astramolecula-dev"; then
        container_name="astramolecula-dev"
    fi
    
    log_info "Entering shell in $container_name..."
    docker exec -it "$container_name" /bin/bash
}

# 清理
clean_up() {
    log_warn "This will remove all AstraMolecula containers, images, and volumes."
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        cd "$DOCKER_DIR"
        docker compose down -v --rmi local 2>/dev/null || true
        docker compose -f docker-compose.dev.yml down -v --rmi local 2>/dev/null || true
        log_info "Cleanup completed!"
    else
        log_info "Cleanup cancelled."
    fi
}

# 测试健康状态
test_health() {
    log_info "Testing service health..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_info "✅ Service is healthy!"
            curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
            return 0
        fi
        
        echo -ne "\r${YELLOW}[WAIT]${NC} Waiting for service... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    echo ""
    log_error "❌ Service health check failed after $max_attempts attempts"
    log_info "Check logs with: $0 logs"
    return 1
}

# 主函数
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    local command=$1
    shift
    
    case $command in
        build)
            build_image
            ;;
        start)
            start_services "$@"
            ;;
        start-dev)
            start_dev "$@"
            ;;
        stop)
            stop_services
            ;;
        logs)
            view_logs "$@"
            ;;
        shell)
            enter_shell
            ;;
        clean)
            clean_up
            ;;
        test)
            test_health
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
