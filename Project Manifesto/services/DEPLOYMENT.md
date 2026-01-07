# 部署指南

## 概述

本文档提供 Quark Media System 的完整部署指南，包括环境准备、一键部署、手动部署和故障排查。

## 系统要求

### 硬件要求
- CPU: 4核心或更高
- 内存: 8GB 或更高
- 磁盘: 50GB 可用空间（根据媒体文件大小调整）

### 软件要求
- Docker 20.10 或更高
- Docker Compose 2.0 或更高
- Python 3.9+ (仅用于本地开发)

### 操作系统
- Linux (推荐 Ubuntu 20.04+)
- macOS 10.15+
- Windows 10/11 (WSL2 推荐)

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/Quark-Media-System.git
cd Quark-Media-System
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置以下必需变量：

```env
QUARK_COOKIE=your_quark_cookie_here
WEBDAV_AUTH_USER=admin
WEBDAV_AUTH_PASSWORD=your_password_here
POSTGRES_PASSWORD=your_postgres_password
```

### 3. 一键部署

**Linux/macOS:**
```bash
cd services
chmod +x deploy.sh
./deploy.sh
```

**Windows (PowerShell):**
```powershell
cd services
.\deploy.ps1
```

部署脚本将自动完成以下操作：
1. 检查环境
2. 创建必要的目录
3. 构建镜像
4. 启动服务
5. 等待健康检查

### 4. 验证部署

访问以下地址验证服务是否正常运行：

- **WebDAV**: http://localhost:5244
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 手动部署

### 1. 创建数据目录

```bash
mkdir -p data/webdav_cache
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p services/backups
```

### 2. 构建镜像

```bash
docker-compose build
```

### 3. 启动服务

```bash
docker-compose up -d
```

### 4. 检查服务状态

```bash
docker-compose ps
```

### 5. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f core-backend
docker-compose logs -f worker
docker-compose logs -f quarkdrive-webdav
```

## 优化部署

使用优化后的 Docker Compose 配置：

```bash
docker-compose -f docker-compose.optimized.yml up -d
```

优化配置包括：
- 健康检查
- 资源限制
- 自动重启
- 依赖管理
- 网络隔离

## 服务管理

### 启动服务

```bash
docker-compose up -d
```

### 停止服务

```bash
docker-compose stop
```

### 重启服务

```bash
docker-compose restart
```

### 重启特定服务

```bash
docker-compose restart core-backend
docker-compose restart worker
```

### 停止并删除容器

```bash
docker-compose down
```

### 停止并删除容器和数据卷

```bash
docker-compose down -v
```

### 重新构建并启动

```bash
docker-compose up -d --build
```

## 数据库管理

### 备份数据库

**Linux/macOS:**
```bash
cd services
python backup_db.py
```

**Windows (PowerShell):**
```powershell
cd services
.\backup_db.ps1
```

### 恢复数据库

**Linux/macOS:**
```bash
python backup_db.py restore backups/quark_media_YYYYMMDD_HHMMSS.sql
```

**Windows (PowerShell):**
```powershell
.\backup_db.ps1 restore backups\quark_media_YYYYMMDD_HHMMSS.sql
```

### 执行数据库迁移

```bash
docker-compose exec core-backend alembic upgrade head
```

## 监控和日志

### 查看实时日志

```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f core-backend
docker-compose logs -f worker
docker-compose logs -f quarkdrive-webdav
docker-compose logs -f postgres
docker-compose logs -f redis
```

### 查看容器资源使用

```bash
docker stats
```

### 查看容器详细信息

```bash
docker inspect quark-backend
docker inspect quark-worker
```

### 进入容器

```bash
# 进入后端容器
docker-compose exec core-backend bash

# 进入 Worker 容器
docker-compose exec worker bash

# 进入 PostgreSQL 容器
docker-compose exec postgres psql -U quark -d quark_media

# 进入 Redis 容器
docker-compose exec redis redis-cli
```

## 环境变量配置

### 核心配置

```env
# Quark Cookie (必需)
QUARK_COOKIE=your_quark_cookie_here

# WebDAV 认证
WEBDAV_AUTH_USER=admin
WEBDAV_AUTH_PASSWORD=your_password_here

# 数据库配置
POSTGRES_PASSWORD=your_postgres_password
DATABASE_URL=postgresql+asyncpg://quark:password@postgres:5432/quark_media

# Redis 配置
REDIS_URL=redis://redis:6379/0
```

### 传输配置

```env
# 最大重试次数
MAX_RETRY_COUNT=3

# Cookie 验证间隔（秒）
COOKIE_VALIDATION_INTERVAL=3600

# 目标目录模式
TRANSFER_DEST_DIR_PATTERN=/QuarkMedia/{type}/{year}/{title}({year})

# share_save fid 字段覆写（当部分分享要求不同字段时）
QUARK_SHARE_SAVE_FID_FIELD=fid_list

# share_save 目标 host（可单个或逗号分隔列表）
QUARK_SHARE_SAVE_BASE_URL=
QUARK_SHARE_SAVE_BASE_URLS=
QUARK_SHARE_SAVE_USE_SAFE_HOST=1

# Quark 媒体根目录
QUARK_MEDIA_ROOT=/QuarkMedia

# Worker 并发数
WORKER_CONCURRENCY=5
```

### 日志配置

```env
# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

## 性能优化

### 1. 调整 Worker 并发数

根据服务器性能调整 `WORKER_CONCURRENCY`：

```env
# 低配置服务器
WORKER_CONCURRENCY=2

# 中等配置服务器
WORKER_CONCURRENCY=5

# 高配置服务器
WORKER_CONCURRENCY=10
```

### 2. 调整 Redis 内存

编辑 `docker-compose.optimized.yml`：

```yaml
redis:
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### 3. 调整 PostgreSQL 配置

创建 `data/postgres/postgresql.conf`：

```ini
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB
```

### 4. 启用连接池

后端服务已内置连接池，无需额外配置。

## 故障排查

### 服务无法启动

1. 检查端口占用：
```bash
netstat -tuln | grep -E '5244|8000|6379|5432'
```

2. 查看服务日志：
```bash
docker-compose logs [service_name]
```

3. 检查磁盘空间：
```bash
df -h
```

### 数据库连接失败

1. 检查 PostgreSQL 是否运行：
```bash
docker-compose ps postgres
docker-compose logs postgres
```

2. 测试数据库连接：
```bash
docker-compose exec postgres pg_isready -U quark -d quark_media
```

3. 检查环境变量：
```bash
docker-compose exec core-backend env | grep DATABASE_URL
```

### Worker 不处理任务

1. 检查 Worker 日志：
```bash
docker-compose logs worker
```

2. 检查 Redis 队列：
```bash
docker-compose exec redis redis-cli LLEN queue:transfer
```

3. 检查死信队列：
```bash
docker-compose exec redis redis-cli LLEN queue:transfer:dead
```

### Cookie 失效

1. 更新 Cookie：
```bash
curl -X POST http://localhost:8000/api/cookie/update \
  -H "Content-Type: application/json" \
  -d '{"cookie": "new_cookie_here"}'
```

2. 验证 Cookie：
```bash
curl http://localhost:8000/api/cookie/validate
```

### 性能问题

1. 查看资源使用：
```bash
docker stats
```

2. 检查慢查询：
```bash
docker-compose exec postgres psql -U quark -d quark_media -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

3. 调整并发数和资源限制。

## 安全建议

1. **更改默认密码**
   - 修改 `WEBDAV_AUTH_PASSWORD`
   - 修改 `POSTGRES_PASSWORD`

2. **使用 HTTPS**
   - 配置反向代理（Nginx）
   - 使用 Let's Encrypt 证书

3. **限制网络访问**
   - 使用防火墙限制端口访问
   - 仅暴露必要的端口

4. **定期备份**
   - 设置自动备份任务
   - 保留多个备份版本

5. **监控日志**
   - 定期检查异常日志
   - 设置告警机制

## 升级

### 升级到新版本

```bash
# 1. 备份数据
cd services
python backup_db.py

# 2. 拉取最新代码
git pull origin main

# 3. 重新构建镜像
docker-compose build

# 4. 执行数据库迁移
docker-compose exec core-backend alembic upgrade head

# 5. 重启服务
docker-compose up -d
```

### 回滚到旧版本

```bash
# 1. 停止服务
docker-compose down

# 2. 切换到旧版本
git checkout <old_version_tag>

# 3. 恢复数据库
python backup_db.py restore backups/quark_media_YYYYMMDD_HHMMSS.sql

# 4. 重新构建并启动
docker-compose up -d --build
```

## 生产环境部署

### 使用 Docker Swarm

```bash
docker swarm init
docker stack deploy -c docker-compose.optimized.yml quark-media
```

### 使用 Kubernetes

参考 `k8s/` 目录下的 Kubernetes 配置文件。

### 负载均衡

使用 Nginx 或 HAProxy 进行负载均衡：

```nginx
upstream backend {
    server quark-backend-1:8000;
    server quark-backend-2:8000;
    server quark-backend-3:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 支持

如有问题，请：
1. 查看日志文件
2. 检查故障排查部分
3. 提交 Issue 到 GitHub
4. 联系技术支持
