#!/bin/bash
set -e

echo "============================================"
echo "  虾虾工厂 - XiaXia Factory 部署脚本"
echo "============================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "[ERROR] Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 判断使用哪个 compose 命令
COMPOSE_CMD="docker compose"
if ! command -v docker compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
fi

MODE="${1:-dev}"
COMPOSE_FILES=(-f docker-compose.yml)
FRONTEND_URL="http://localhost:${FRONTEND_PORT:-10088}"
BACKEND_URL="http://localhost:5000"
DATABASE_HINT="localhost:3306"

if [ "$MODE" = "prod" ]; then
    COMPOSE_FILES+=(-f docker-compose.prod.yml)
    FRONTEND_URL="http://localhost:${FRONTEND_PORT:-80}"
    BACKEND_URL="通过前端网关 ${FRONTEND_URL}/api"
    DATABASE_HINT="不对公网暴露"
fi

echo ""
echo "[1/5] 停止旧容器（如果存在）..."
$COMPOSE_CMD "${COMPOSE_FILES[@]}" down 2>/dev/null || true

echo ""
echo "[2/5] 构建镜像..."
$COMPOSE_CMD "${COMPOSE_FILES[@]}" build

echo ""
echo "[3/5] 启动数据库..."
$COMPOSE_CMD "${COMPOSE_FILES[@]}" up -d db

echo ""
echo "[4/5] 等待数据库就绪..."
for i in {1..30}; do
    if $COMPOSE_CMD "${COMPOSE_FILES[@]}" exec -T db mysqladmin ping -h localhost --silent >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

if ! $COMPOSE_CMD "${COMPOSE_FILES[@]}" exec -T db mysqladmin ping -h localhost --silent >/dev/null 2>&1; then
    echo "[ERROR] 数据库未能在预期时间内启动"
    exit 1
fi

echo ""
echo "[5/5] 执行数据库迁移并启动应用..."
$COMPOSE_CMD "${COMPOSE_FILES[@]}" run --rm backend python manage.py migrate
$COMPOSE_CMD "${COMPOSE_FILES[@]}" up -d backend frontend

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "  部署模式:  $MODE"
echo "  前端地址:  $FRONTEND_URL"
echo "  后端API:   $BACKEND_URL"
echo "  数据库:    $DATABASE_HINT"
if [ "$MODE" = "prod" ]; then
    echo "  管理员初始化: 首次启动会读取 ADMIN_INIT_* 环境变量创建一次性管理员"
    echo "  迁移策略: 已在启动前执行 python manage.py migrate"
fi
echo ""
echo "  查看日志:  $COMPOSE_CMD ${COMPOSE_FILES[*]} logs -f"
echo "  停止服务:  $COMPOSE_CMD ${COMPOSE_FILES[*]} down"
echo "============================================"
