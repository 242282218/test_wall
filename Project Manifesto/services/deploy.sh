#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "  Quark Media System 一键部署脚本"
echo "======================================"
echo ""

cd "$PROJECT_ROOT"

echo "[1/7] 检查环境..."
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    exit 1
fi

echo "✓ Docker 和 Docker Compose 已安装"
echo ""

echo "[2/7] 检查环境变量..."
if [ ! -f .env ]; then
    echo "警告: .env 文件不存在，从 .env.example 创建"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ 已创建 .env 文件"
        echo "请编辑 .env 文件并设置必要的变量，特别是 QUARK_COOKIE"
        read -p "按 Enter 继续..."
    else
        echo "错误: .env.example 文件不存在"
        exit 1
    fi
else
    echo "✓ .env 文件已存在"
fi

if ! grep -q "QUARK_COOKIE=" .env || grep -q "QUARK_COOKIE=$" .env; then
    echo "警告: QUARK_COOKIE 未设置"
    echo "请在 .env 文件中设置 QUARK_COOKIE"
    exit 1
fi

echo "✓ 环境变量检查完成"
echo ""

echo "[3/7] 创建必要的目录..."
mkdir -p data/webdav_cache
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p services/backups
echo "✓ 目录创建完成"
echo ""

echo "[4/7] 停止现有容器..."
docker-compose down 2>/dev/null || true
echo "✓ 容器已停止"
echo ""

echo "[5/7] 构建镜像..."
docker-compose build
echo "✓ 镜像构建完成"
echo ""

echo "[6/7] 启动服务..."
docker-compose up -d
echo "✓ 服务已启动"
echo ""

echo "[7/7] 等待服务健康检查..."
echo "等待 PostgreSQL..."
timeout 60 bash -c 'until docker-compose exec -T postgres pg_isready -U quark -d quark_media; do sleep 2; done' || {
    echo "错误: PostgreSQL 启动超时"
    docker-compose logs postgres
    exit 1
}
echo "✓ PostgreSQL 已就绪"

echo "等待 Redis..."
timeout 30 bash -c 'until docker-compose exec -T redis redis-cli ping | grep -q PONG; do sleep 1; done' || {
    echo "错误: Redis 启动超时"
    docker-compose logs redis
    exit 1
}
echo "✓ Redis 已就绪"

echo "等待 WebDAV..."
timeout 60 bash -c 'until curl -sf http://localhost:5244/health > /dev/null 2>&1; do sleep 2; done' || {
    echo "警告: WebDAV 健康检查超时，但服务可能仍在启动"
}
echo "✓ WebDAV 已就绪"

echo "等待后端 API..."
timeout 60 bash -c 'until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done' || {
    echo "警告: 后端 API 健康检查超时，但服务可能仍在启动"
}
echo "✓ 后端 API 已就绪"

echo ""
echo "======================================"
echo "  部署完成！"
echo "======================================"
echo ""
echo "服务访问地址:"
echo "  - WebDAV:     http://localhost:5244"
echo "  - 后端 API:   http://localhost:8000"
echo "  - API 文档:   http://localhost:8000/docs"
echo "  - Redis:      localhost:6379"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "常用命令:"
echo "  查看日志:     docker-compose logs -f [service_name]"
echo "  停止服务:     docker-compose stop"
echo "  重启服务:     docker-compose restart"
echo "  完全清理:     docker-compose down -v"
echo ""
echo "容器状态:"
docker-compose ps
echo ""
