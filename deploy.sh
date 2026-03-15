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

echo ""
echo "[1/3] 停止旧容器（如果存在）..."
$COMPOSE_CMD down 2>/dev/null || true

echo ""
echo "[2/3] 构建并启动所有服务..."
$COMPOSE_CMD up --build -d

echo ""
echo "[3/3] 等待服务启动..."
sleep 5

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "  前端地址:  http://localhost"
echo "  后端API:   http://localhost:5000"
echo "  数据库:    localhost:3306"
echo ""
echo "  查看日志:  $COMPOSE_CMD logs -f"
echo "  停止服务:  $COMPOSE_CMD down"
echo "============================================"
