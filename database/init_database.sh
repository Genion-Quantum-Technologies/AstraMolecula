#!/bin/bash
# ============================================================
# AstraMolecula 数据库初始化脚本
# 用法: bash init_database.sh [选项]
# 
# 选项:
#   -h, --host      数据库主机 (默认: 127.0.0.1)
#   -u, --user      数据库用户 (默认: root)
#   -p, --password  数据库密码 (如不提供将提示输入)
#   --skip-create   跳过创建数据库和用户，仅创建表
# ============================================================

set -e

# 默认配置
DB_HOST="127.0.0.1"
DB_USER="root"
DB_PASSWORD=""
SKIP_CREATE=false

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/init_database.sql"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 帮助信息
show_help() {
    echo "AstraMolecula 数据库初始化脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --host HOST       数据库主机地址 (默认: 127.0.0.1)"
    echo "  -u, --user USER       数据库管理员用户名 (默认: root)"
    echo "  -p, --password PWD    数据库管理员密码"
    echo "  --skip-create         跳过创建数据库和用户，仅创建表结构"
    echo "  --help                显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                           # 使用默认配置，交互式输入密码"
    echo "  $0 -p mypassword             # 使用root用户和指定密码"
    echo "  $0 -u admin -p pwd123        # 使用指定用户和密码"
    echo "  $0 --skip-create             # 仅创建表（数据库和用户已存在）"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -u|--user)
            DB_USER="$2"
            shift 2
            ;;
        -p|--password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --skip-create)
            SKIP_CREATE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}错误: 未知参数 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 检查 SQL 文件是否存在
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}错误: SQL 文件不存在: ${SQL_FILE}${NC}"
    exit 1
fi

# 如果未提供密码，提示输入
if [ -z "$DB_PASSWORD" ]; then
    echo -n "请输入数据库密码 ($DB_USER@$DB_HOST): "
    read -s DB_PASSWORD
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AstraMolecula 数据库初始化${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "数据库主机: $DB_HOST"
echo "管理员用户: $DB_USER"
echo ""

# 构建 MySQL 命令
MYSQL_CMD="mysql -h $DB_HOST -u $DB_USER"
if [ -n "$DB_PASSWORD" ]; then
    MYSQL_CMD="$MYSQL_CMD -p$DB_PASSWORD"
fi

# 测试数据库连接
echo -e "${YELLOW}[1/3] 测试数据库连接...${NC}"
if ! $MYSQL_CMD -e "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}错误: 无法连接到数据库${NC}"
    echo "请检查:"
    echo "  1. MySQL 服务是否运行"
    echo "  2. 用户名和密码是否正确"
    echo "  3. 主机地址是否正确"
    exit 1
fi
echo -e "${GREEN}数据库连接成功！${NC}"
echo ""

if [ "$SKIP_CREATE" = true ]; then
    # 仅创建表结构（使用 vina_user 连接已存在的 project1 数据库）
    echo -e "${YELLOW}[2/3] 跳过创建数据库和用户...${NC}"
    echo -e "${YELLOW}[3/3] 创建表结构...${NC}"
    
    # 只执行表创建部分（跳过前面的 CREATE DATABASE 和 CREATE USER）
    # 使用 vina_user 连接
    VINA_MYSQL_CMD="mysql -h $DB_HOST -u vina_user -pAa7758258123 project1"
    
    # 创建一个临时 SQL 文件，只包含 USE 和 CREATE TABLE 语句
    TEMP_SQL=$(mktemp)
    sed -n '/^USE project1;/,$p' "$SQL_FILE" > "$TEMP_SQL"
    
    if $VINA_MYSQL_CMD < "$TEMP_SQL" 2>&1; then
        echo -e "${GREEN}表结构创建成功！${NC}"
    else
        echo -e "${RED}表结构创建失败！${NC}"
        rm -f "$TEMP_SQL"
        exit 1
    fi
    rm -f "$TEMP_SQL"
else
    # 完整初始化（创建数据库、用户和表）
    echo -e "${YELLOW}[2/3] 创建数据库和用户...${NC}"
    echo -e "${YELLOW}[3/3] 创建表结构...${NC}"
    
    if $MYSQL_CMD < "$SQL_FILE" 2>&1; then
        echo -e "${GREEN}数据库初始化成功！${NC}"
    else
        echo -e "${RED}数据库初始化失败！${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}初始化完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "数据库信息:"
echo "  数据库名: project1"
echo "  用户名:   vina_user"
echo "  密码:     Aa7758258123"
echo "  主机:     $DB_HOST"
echo ""
echo "连接命令:"
echo "  mysql -u vina_user -p -h $DB_HOST project1"
echo ""
echo "创建的表:"
echo "  - users              (用户表)"
echo "  - user_uploads       (用户上传文件表)"
echo "  - tasks              (任务表)"
echo "  - docking_task_params    (Docking任务参数表)"
echo "  - peptide_task_params    (Peptide任务参数表)"
echo "  - service_user_mappings  (服务用户映射表)"
