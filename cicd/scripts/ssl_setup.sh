#!/bin/bash

# ============================================================
# AstraMolecula SSL 证书配置脚本
# 用于在云服务器上配置 Nginx SSL
# ============================================================

set -e

# ================== 配置变量 ==================
# 请根据实际情况修改以下变量

DOMAIN="api.genionaitech.com"          # 你的子域名（修改为实际使用的子域名）
SERVER_IP="3.133.131.124"              # 云服务器 IP
BACKEND_PORT=8000                       # AutoSSH 隧道转发的端口

# SSL 证书路径（在云服务器上）
SSL_CERT_PATH="/etc/nginx/ssl/genionaitech.com.crt"
SSL_KEY_PATH="/etc/nginx/ssl/genionaitech.com.key"

# Nginx 配置路径
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
NGINX_CONFIG_FILE="$NGINX_SITES_AVAILABLE/astramolecula"

# ================== 颜色定义 ==================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# ================== 检查 Root 权限 ==================
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "请使用 root 权限运行此脚本"
        echo "使用方法: sudo $0"
        exit 1
    fi
}

# ================== 检查 SSL 证书 ==================
check_ssl_certificates() {
    log "检查 SSL 证书文件..."
    
    if [ ! -f "$SSL_CERT_PATH" ]; then
        error "证书文件不存在: $SSL_CERT_PATH"
        echo ""
        echo "请先上传证书文件:"
        echo "  sudo mkdir -p /etc/nginx/ssl"
        echo "  sudo cp fullchain.cer $SSL_CERT_PATH"
        echo "  sudo cp _.genionaitech.com.key $SSL_KEY_PATH"
        echo "  sudo chmod 600 /etc/nginx/ssl/*"
        exit 1
    fi
    
    if [ ! -f "$SSL_KEY_PATH" ]; then
        error "私钥文件不存在: $SSL_KEY_PATH"
        exit 1
    fi
    
    log "✅ SSL 证书文件检查通过"
}

# ================== 安装 Nginx ==================
install_nginx() {
    if command -v nginx &> /dev/null; then
        log "Nginx 已安装"
        return
    fi
    
    log "安装 Nginx..."
    
    if command -v apt &> /dev/null; then
        apt update && apt install -y nginx
    elif command -v yum &> /dev/null; then
        yum install -y epel-release && yum install -y nginx
    elif command -v dnf &> /dev/null; then
        dnf install -y nginx
    else
        error "无法识别的包管理器"
        exit 1
    fi
    
    systemctl enable nginx
    systemctl start nginx
    log "✅ Nginx 安装完成"
}

# ================== 创建 Nginx SSL 配置 ==================
create_nginx_ssl_config() {
    log "创建 Nginx SSL 配置..."
    
    # 备份现有配置
    if [ -f "$NGINX_CONFIG_FILE" ]; then
        cp "$NGINX_CONFIG_FILE" "$NGINX_CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        warn "已备份现有配置"
    fi
    
    # 创建配置文件
    cat > "$NGINX_CONFIG_FILE" << 'EOF'
# ============================================================
# AstraMolecula Nginx SSL 配置
# 生成时间: GENERATED_TIME
# ============================================================

# 上游服务定义（通过 AutoSSH 隧道连接到本地服务）
upstream astramolecula_backend {
    server 127.0.0.1:BACKEND_PORT_PLACEHOLDER;
    keepalive 32;
    keepalive_requests 100;
    keepalive_timeout 60s;
}

# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    
    # Let's Encrypt 验证路径（如果需要）
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # 其他所有请求重定向到 HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS 服务器
server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;
    
    # ============ SSL 证书配置 ============
    ssl_certificate SSL_CERT_PLACEHOLDER;
    ssl_certificate_key SSL_KEY_PLACEHOLDER;
    
    # ============ SSL 安全配置 ============
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # OCSP Stapling（提高性能）
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
    
    # ============ 安全头部 ============
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    # 注意: X-Frame-Options 在全局移除，改为在特定 location 中设置
    # 这样可以允许 /public/* 路由被第三方网站通过 iframe 嵌入
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # ============ CORS 配置 ============
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, X-API-Key, Content-Type, Accept, Origin, User-Agent, DNT, Cache-Control, X-Mx-ReqToken, Keep-Alive, X-Requested-With, If-Modified-Since' always;
    
    # 处理 OPTIONS 预检请求
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, X-API-Key, Content-Type, Accept, Origin, User-Agent, DNT, Cache-Control, X-Mx-ReqToken, Keep-Alive, X-Requested-With, If-Modified-Since';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }
    
    # ============ 日志配置 ============
    access_log /var/log/nginx/astramolecula.access.log;
    error_log /var/log/nginx/astramolecula.error.log;
    
    # ============ 公开访问路径 (允许 iframe 嵌入) ============
    # 这些路径供第三方网站通过 iframe 嵌入查看 3D 分子结构
    location ~ ^/public/ {
        client_max_body_size 100M;
        
        proxy_pass http://astramolecula_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # 允许任何网站通过 iframe 嵌入这些公开页面
        # 使用 Content-Security-Policy 的 frame-ancestors 替代 X-Frame-Options
        add_header Content-Security-Policy "frame-ancestors *" always;
        add_header 'Access-Control-Allow-Origin' '*' always;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 300s;
    }
    
    # ============ 主要 API 代理 ============
    location / {
        client_max_body_size 100M;  # 允许最大 100MB 文件上传
        
        # 非公开路径禁止 iframe 嵌入
        add_header X-Frame-Options "SAMEORIGIN" always;
        
        proxy_pass http://astramolecula_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 300s;  # 长时间任务需要较长超时
        
        # 缓冲设置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # ============ 文件上传配置 ============
    location ~ ^/(uploads|api/.*upload) {
        client_max_body_size 100M;
        
        proxy_pass http://astramolecula_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 上传超时
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # 禁用缓冲以支持大文件上传
        proxy_request_buffering off;
    }
    
    # ============ 健康检查 ============
    location /health {
        proxy_pass http://astramolecula_backend/health;
        proxy_set_header Host $host;
        access_log off;
    }
    
    # ============ API 文档 ============
    location /docs {
        proxy_pass http://astramolecula_backend/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /openapi.json {
        proxy_pass http://astramolecula_backend/openapi.json;
        proxy_set_header Host $host;
    }
    
    location /redoc {
        proxy_pass http://astramolecula_backend/redoc;
        proxy_set_header Host $host;
    }
    
    # ============ Gzip 压缩 ============
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

    # 替换占位符
    sed -i "s|GENERATED_TIME|$(date)|g" "$NGINX_CONFIG_FILE"
    sed -i "s|DOMAIN_PLACEHOLDER|$DOMAIN|g" "$NGINX_CONFIG_FILE"
    sed -i "s|BACKEND_PORT_PLACEHOLDER|$BACKEND_PORT|g" "$NGINX_CONFIG_FILE"
    sed -i "s|SSL_CERT_PLACEHOLDER|$SSL_CERT_PATH|g" "$NGINX_CONFIG_FILE"
    sed -i "s|SSL_KEY_PLACEHOLDER|$SSL_KEY_PATH|g" "$NGINX_CONFIG_FILE"
    
    log "✅ Nginx SSL 配置文件已创建: $NGINX_CONFIG_FILE"
}

# ================== 启用站点 ==================
enable_site() {
    log "启用站点配置..."
    
    # 确保 sites-enabled 目录存在
    mkdir -p "$NGINX_SITES_ENABLED"
    
    # 删除默认站点（如果存在）
    if [ -f "$NGINX_SITES_ENABLED/default" ]; then
        rm -f "$NGINX_SITES_ENABLED/default"
        log "已禁用默认站点"
    fi
    
    # 创建符号链接
    ln -sf "$NGINX_CONFIG_FILE" "$NGINX_SITES_ENABLED/"
    
    # 测试配置
    log "测试 Nginx 配置..."
    if nginx -t; then
        log "✅ Nginx 配置测试通过"
    else
        error "❌ Nginx 配置测试失败"
        exit 1
    fi
    
    # 重载 Nginx
    systemctl reload nginx
    log "✅ Nginx 已重载"
}

# ================== 配置防火墙 ==================
configure_firewall() {
    log "配置防火墙..."
    
    # UFW (Ubuntu/Debian)
    if command -v ufw &> /dev/null; then
        ufw allow 80/tcp
        ufw allow 443/tcp
        log "UFW 防火墙规则已配置"
    fi
    
    # Firewalld (CentOS/RHEL)
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        log "Firewalld 防火墙规则已配置"
    fi
    
    # iptables
    if command -v iptables &> /dev/null && ! command -v ufw &> /dev/null && ! command -v firewall-cmd &> /dev/null; then
        iptables -A INPUT -p tcp --dport 80 -j ACCEPT
        iptables -A INPUT -p tcp --dport 443 -j ACCEPT
        log "iptables 防火墙规则已配置"
    fi
}

# ================== 显示配置信息 ==================
show_info() {
    echo ""
    echo "=============================================="
    echo "  🔐 AstraMolecula SSL 配置完成"
    echo "=============================================="
    echo ""
    echo "📋 配置信息:"
    echo "  域名: $DOMAIN"
    echo "  HTTP:  http://$DOMAIN  → 重定向到 HTTPS"
    echo "  HTTPS: https://$DOMAIN"
    echo ""
    echo "📁 文件位置:"
    echo "  Nginx 配置: $NGINX_CONFIG_FILE"
    echo "  SSL 证书:   $SSL_CERT_PATH"
    echo "  SSL 私钥:   $SSL_KEY_PATH"
    echo ""
    echo "📊 日志文件:"
    echo "  访问日志: /var/log/nginx/astramolecula.access.log"
    echo "  错误日志: /var/log/nginx/astramolecula.error.log"
    echo ""
    echo "🔧 常用命令:"
    echo "  查看状态:   systemctl status nginx"
    echo "  重载配置:   sudo systemctl reload nginx"
    echo "  测试配置:   sudo nginx -t"
    echo "  查看日志:   tail -f /var/log/nginx/astramolecula.error.log"
    echo ""
    echo "✅ 下一步:"
    echo "  1. 确保域名 $DOMAIN 已解析到 $SERVER_IP"
    echo "  2. 确保 AutoSSH 隧道正在运行"
    echo "  3. 测试访问: curl -I https://$DOMAIN/health"
    echo "=============================================="
}

# ================== 测试配置 ==================
test_config() {
    log "测试 SSL 配置..."
    
    # 测试 Nginx 配置语法
    if nginx -t; then
        log "✅ Nginx 配置语法正确"
    else
        error "❌ Nginx 配置语法错误"
        return 1
    fi
    
    # 测试 HTTPS 连接
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://$DOMAIN/health" 2>/dev/null | grep -q "200\|301\|302"; then
        log "✅ HTTPS 连接正常"
    else
        warn "⚠️  HTTPS 连接测试失败，请检查:"
        echo "    1. DNS 是否已解析到 $SERVER_IP"
        echo "    2. AutoSSH 隧道是否正在运行"
        echo "    3. 后端服务是否已启动"
    fi
    
    # 测试 SSL 证书
    log "SSL 证书信息:"
    echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || warn "无法获取证书信息"
}

# ================== 上传证书辅助函数 ==================
upload_certs_help() {
    echo ""
    echo "=============================================="
    echo "  📤 SSL 证书上传指南"
    echo "=============================================="
    echo ""
    echo "请在本地机器上执行以下命令上传证书到云服务器:"
    echo ""
    echo "# 1. 创建 SSL 目录"
    echo "ssh root@$SERVER_IP 'mkdir -p /etc/nginx/ssl && chmod 700 /etc/nginx/ssl'"
    echo ""
    echo "# 2. 上传证书文件"
    echo "scp /home/songyou/projects/SSL/fullchain.cer root@$SERVER_IP:$SSL_CERT_PATH"
    echo "scp /home/songyou/projects/SSL/_.genionaitech.com.key root@$SERVER_IP:$SSL_KEY_PATH"
    echo ""
    echo "# 3. 设置权限"
    echo "ssh root@$SERVER_IP 'chmod 600 /etc/nginx/ssl/*'"
    echo ""
    echo "# 4. 然后在云服务器上运行此脚本"
    echo "=============================================="
}

# ================== 主函数 ==================
main() {
    case "${1:-install}" in
        install)
            log "开始配置 AstraMolecula SSL..."
            check_root
            check_ssl_certificates
            install_nginx
            create_nginx_ssl_config
            enable_site
            configure_firewall
            show_info
            ;;
        test)
            test_config
            ;;
        help)
            upload_certs_help
            ;;
        info)
            show_info
            ;;
        *)
            echo "用法: $0 {install|test|help|info}"
            echo ""
            echo "命令:"
            echo "  install  安装并配置 SSL (默认)"
            echo "  test     测试当前配置"
            echo "  help     显示证书上传指南"
            echo "  info     显示配置信息"
            exit 1
            ;;
    esac
}

main "$@"
