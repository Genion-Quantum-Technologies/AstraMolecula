#!/bin/bash

# 云服务器Nginx安装和配置脚本
# 用于在云服务器上安装Nginx并配置DockingVina服务代理

set -e

# 配置变量
DOMAIN="106.14.212.218"                    # 您的云服务器公网IP地址
SERVER_NAME="$DOMAIN"                       # Nginx server_name
DOCKING_PORT=8000                          # DockingVina服务端口
SSL_ENABLED=false                          # 禁用SSL (阿里云服务器，无SSL证书)
EMAIL="your-email@example.com"             # SSL证书邮箱(未使用)

# 路径配置
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
NGINX_CONFIG_FILE="$NGINX_SITES_AVAILABLE/docking-vina"
LOG_DIR="/var/log/nginx"

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

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "请使用root权限运行此脚本"
        echo "使用方法: sudo $0"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        error "无法检测操作系统"
        exit 1
    fi
    
    log "检测到操作系统: $OS $VERSION"
}

# 更新系统包
update_system() {
    log "更新系统包..."
    
    case $OS in
        ubuntu|debian)
            apt update && apt upgrade -y
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                dnf update -y
            else
                yum update -y
            fi
            ;;
        *)
            warn "未知的操作系统，跳过系统更新"
            ;;
    esac
}

# 安装Nginx
install_nginx() {
    log "安装Nginx..."
    
    case $OS in
        ubuntu|debian)
            apt install -y nginx
            ;;
        centos|rhel|almalinux|rocky)
            if command -v dnf &> /dev/null; then
                dnf install -y nginx
            else
                yum install -y epel-release
                yum install -y nginx
            fi
            ;;
        fedora)
            dnf install -y nginx
            ;;
        # 阿里云ECS支持多种操作系统
        *)
            # 尝试自动检测包管理器
            if command -v apt &> /dev/null; then
                log "检测到apt包管理器，使用Debian/Ubuntu安装方式"
                apt install -y nginx
            elif command -v yum &> /dev/null; then
                log "检测到yum包管理器，使用CentOS/RHEL安装方式"
                yum install -y epel-release
                yum install -y nginx
            elif command -v dnf &> /dev/null; then
                log "检测到dnf包管理器，使用Fedora安装方式"
                dnf install -y nginx
            else
                error "无法识别的包管理器，请手动安装nginx"
                exit 1
            fi
            ;;
    esac
    
    # 启动并启用Nginx
    systemctl start nginx
    systemctl enable nginx
    
    log "✅ Nginx安装完成"
}

# 配置防火墙
configure_firewall() {
    log "配置防火墙..."
    
    # 检查并配置ufw (Ubuntu/Debian)
    if command -v ufw &> /dev/null; then
        ufw allow 'Nginx Full'
        ufw allow ssh
        log "UFW防火墙规则已配置"
    fi
    
    # 检查并配置firewalld (CentOS/RHEL/Fedora)
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --reload
        log "Firewalld防火墙规则已配置"
    fi
    
    # 检查并配置iptables
    if command -v iptables &> /dev/null && ! command -v ufw &> /dev/null && ! command -v firewall-cmd &> /dev/null; then
        iptables -A INPUT -p tcp --dport 80 -j ACCEPT
        iptables -A INPUT -p tcp --dport 443 -j ACCEPT
        iptables -A INPUT -p tcp --dport 22 -j ACCEPT
        # 保存iptables规则
        if command -v iptables-save &> /dev/null; then
            iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi
        log "Iptables防火墙规则已配置"
    fi
}

# 创建Nginx配置文件
create_nginx_config() {
    log "创建Nginx配置文件..."
    
    # 备份现有配置
    if [ -f "$NGINX_CONFIG_FILE" ]; then
        cp "$NGINX_CONFIG_FILE" "$NGINX_CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        warn "已备份现有配置文件"
    fi
    
    # 创建新配置
    cat > "$NGINX_CONFIG_FILE" << EOF
# DockingVina API服务配置
# 生成时间: $(date)

# 上游服务定义
upstream docking_backend {
    server localhost:$DOCKING_PORT;
    
    # 健康检查
    keepalive 32;
    keepalive_requests 100;
    keepalive_timeout 60s;
}

# HTTP服务器配置
server {
    listen 80;
    server_name $SERVER_NAME;
    
    # 访问日志
    access_log $LOG_DIR/docking-vina.access.log;
    error_log $LOG_DIR/docking-vina.error.log;
    
    # 安全头部
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # CORS配置
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, X-API-Key, Content-Type, Accept, Origin, User-Agent, DNT, Cache-Control, X-Mx-ReqToken, Keep-Alive, X-Requested-With, If-Modified-Since' always;
    
    # 处理OPTIONS预检请求
    if (\$request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, X-API-Key, Content-Type, Accept, Origin, User-Agent, DNT, Cache-Control, X-Mx-ReqToken, Keep-Alive, X-Requested-With, If-Modified-Since';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }
    
    # 主要API代理
    location / {
        proxy_pass http://docking_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        # 缓冲设置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # API文档特殊处理
    location /docs {
        proxy_pass http://docking_backend/docs;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /openapi.json {
        proxy_pass http://docking_backend/openapi.json;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # 文件上传配置
    location /uploads {
        client_max_body_size 100M;
        proxy_pass http://docking_backend/uploads;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 上传超时
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # 静态文件缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml
        application/rss+xml
        application/atom+xml
        image/svg+xml;
}
EOF

    log "✅ Nginx配置文件已创建: $NGINX_CONFIG_FILE"
}

# 创建SSL配置（如果启用）
create_ssl_config() {
    if [ "$SSL_ENABLED" = "true" ]; then
        log "配置SSL证书..."
        
        # 安装Certbot
        case $OS in
            ubuntu|debian)
                apt install -y certbot python3-certbot-nginx
                ;;
            centos|rhel|fedora)
                if command -v dnf &> /dev/null; then
                    dnf install -y certbot python3-certbot-nginx
                else
                    yum install -y certbot python3-certbot-nginx
                fi
                ;;
        esac
        
        # 获取SSL证书
        certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
        
        log "✅ SSL证书配置完成"
    fi
}

# 启用站点
enable_site() {
    log "启用DockingVina站点..."
    
    # 删除默认站点
    if [ -f "$NGINX_SITES_ENABLED/default" ]; then
        rm -f "$NGINX_SITES_ENABLED/default"
        log "已删除默认站点"
    fi
    
    # 启用新站点
    ln -sf "$NGINX_CONFIG_FILE" "$NGINX_SITES_ENABLED/"
    
    # 测试配置
    if nginx -t; then
        log "✅ Nginx配置测试通过"
    else
        error "❌ Nginx配置测试失败"
        exit 1
    fi
    
    # 重载Nginx
    systemctl reload nginx
    log "✅ Nginx已重载"
}

# 创建监控脚本
create_monitoring_script() {
    log "创建监控脚本..."
    
    cat > "/usr/local/bin/check_docking_service.sh" << 'EOF'
#!/bin/bash

# DockingVina服务健康检查脚本

DOCKING_PORT=8000
LOG_FILE="/var/log/docking_health_check.log"

check_service() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 检查本地DockingVina服务
    if curl -s -f "http://localhost:$DOCKING_PORT/docs" > /dev/null; then
        echo "[$timestamp] ✅ DockingVina服务正常" >> "$LOG_FILE"
        return 0
    else
        echo "[$timestamp] ❌ DockingVina服务异常" >> "$LOG_FILE"
        
        # 发送告警（可以配置邮件或其他通知方式）
        logger "ALERT: DockingVina service is down on port $DOCKING_PORT"
        
        return 1
    fi
}

check_service
EOF
    
    chmod +x "/usr/local/bin/check_docking_service.sh"
    
    # 添加到crontab（每5分钟检查一次）
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/check_docking_service.sh") | crontab -
    
    log "✅ 监控脚本已创建"
}

# 显示配置信息
show_configuration() {
    log "配置完成！"
    echo ""
    echo "================================"
    echo "  DockingVina Nginx配置信息"
    echo "================================"
    echo "服务器名称: $SERVER_NAME"
    echo "后端端口: $DOCKING_PORT"
    echo "SSL启用: $SSL_ENABLED"
    echo "配置文件: $NGINX_CONFIG_FILE"
    echo "访问地址: http://$SERVER_NAME"
    if [ "$SSL_ENABLED" = "true" ]; then
        echo "HTTPS地址: https://$SERVER_NAME"
    fi
    echo "API文档: http://$SERVER_NAME/docs"
    echo ""
    echo "日志文件:"
    echo "  访问日志: $LOG_DIR/docking-vina.access.log"
    echo "  错误日志: $LOG_DIR/docking-vina.error.log"
    echo "  健康检查: /var/log/docking_health_check.log"
    echo ""
    echo "常用命令:"
    echo "  查看Nginx状态: systemctl status nginx"
    echo "  重载Nginx: systemctl reload nginx"
    echo "  查看访问日志: tail -f $LOG_DIR/docking-vina.access.log"
    echo "  查看错误日志: tail -f $LOG_DIR/docking-vina.error.log"
    echo "  测试配置: nginx -t"
    echo ""
    echo "下一步:"
    echo "1. 确保WSL中的DockingVina服务正在运行"
    echo "2. 确保AutoSSH隧道已建立"
    echo "3. 测试API访问: curl http://$SERVER_NAME/docs"
    echo "================================"
}

# 测试配置
test_configuration() {
    log "测试Nginx配置..."
    
    # 测试Nginx配置语法
    if nginx -t; then
        log "✅ Nginx配置语法正确"
    else
        error "❌ Nginx配置语法错误"
        return 1
    fi
    
    # 测试服务连接
    sleep 2
    if curl -s -f "http://localhost/health" > /dev/null; then
        log "✅ 健康检查端点响应正常"
    else
        warn "⚠️  健康检查端点无响应，请确保后端服务正在运行"
    fi
    
    # 测试API文档
    if curl -s -f "http://localhost/docs" > /dev/null; then
        log "✅ API文档端点响应正常"
    else
        warn "⚠️  API文档端点无响应，请检查DockingVina服务"
    fi
}

# 卸载配置
uninstall() {
    log "卸载DockingVina Nginx配置..."
    
    # 禁用站点
    rm -f "$NGINX_SITES_ENABLED/docking-vina"
    
    # 删除配置文件
    rm -f "$NGINX_CONFIG_FILE"
    
    # 删除监控脚本
    rm -f "/usr/local/bin/check_docking_service.sh"
    
    # 删除crontab条目
    crontab -l 2>/dev/null | grep -v "check_docking_service.sh" | crontab -
    
    # 重载Nginx
    systemctl reload nginx
    
    log "✅ 卸载完成"
}

# 主函数
main() {
    case "${1:-install}" in
        install)
            log "开始安装和配置Nginx..."
            check_root
            detect_os
            update_system
            install_nginx
            configure_firewall
            create_nginx_config
            create_ssl_config
            enable_site
            create_monitoring_script
            show_configuration
            ;;
        test)
            log "测试Nginx配置..."
            test_configuration
            ;;
        uninstall)
            check_root
            uninstall
            ;;
        config)
            show_configuration
            ;;
        *)
            echo "用法: $0 {install|test|uninstall|config}"
            echo ""
            echo "命令:"
            echo "  install    安装并配置Nginx (默认)"
            echo "  test       测试当前配置"
            echo "  uninstall  卸载DockingVina配置"
            echo "  config     显示配置信息"
            echo ""
            echo "首次使用前请修改脚本顶部的配置变量"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
