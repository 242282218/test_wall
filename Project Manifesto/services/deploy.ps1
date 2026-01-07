$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Quark Media System 一键部署脚本" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectRoot

Write-Host "[1/7] 检查环境..." -ForegroundColor Yellow
$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "错误: Docker 未安装" -ForegroundColor Red
    exit 1
}

$dockerComposeInstalled = Get-Command docker-compose -ErrorAction SilentlyContinue
if (-not $dockerComposeInstalled) {
    Write-Host "错误: Docker Compose 未安装" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Docker 和 Docker Compose 已安装" -ForegroundColor Green
Write-Host ""

Write-Host "[2/7] 检查环境变量..." -ForegroundColor Yellow
if (-not (Test-Path .env)) {
    Write-Host "警告: .env 文件不存在，从 .env.example 创建" -ForegroundColor Yellow
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "✓ 已创建 .env 文件" -ForegroundColor Green
        Write-Host "请编辑 .env 文件并设置必要的变量，特别是 QUARK_COOKIE" -ForegroundColor Yellow
        Read-Host "按 Enter 继续..."
    } else {
        Write-Host "错误: .env.example 文件不存在" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ .env 文件已存在" -ForegroundColor Green
}

$envContent = Get-Content .env -Raw
if ($envContent -notmatch "QUARK_COOKIE=" -or $envContent -match "QUARK_COOKIE=$") {
    Write-Host "警告: QUARK_COOKIE 未设置" -ForegroundColor Yellow
    Write-Host "请在 .env 文件中设置 QUARK_COOKIE" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 环境变量检查完成" -ForegroundColor Green
Write-Host ""

Write-Host "[3/7] 创建必要的目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path data\webdav_cache | Out-Null
New-Item -ItemType Directory -Force -Path data\postgres | Out-Null
New-Item -ItemType Directory -Force -Path data\redis | Out-Null
New-Item -ItemType Directory -Force -Path services\backups | Out-Null
Write-Host "✓ 目录创建完成" -ForegroundColor Green
Write-Host ""

Write-Host "[4/7] 停止现有容器..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host "✓ 容器已停止" -ForegroundColor Green
Write-Host ""

Write-Host "[5/7] 构建镜像..." -ForegroundColor Yellow
docker-compose build
Write-Host "✓ 镜像构建完成" -ForegroundColor Green
Write-Host ""

Write-Host "[6/7] 启动服务..." -ForegroundColor Yellow
docker-compose up -d
Write-Host "✓ 服务已启动" -ForegroundColor Green
Write-Host ""

Write-Host "[7/7] 等待服务健康检查..." -ForegroundColor Yellow

Write-Host "等待 PostgreSQL..." -ForegroundColor Cyan
$timeout = 60
$elapsed = 0
while ($elapsed -lt $timeout) {
    try {
        $result = docker-compose exec -T postgres pg_isready -U quark -d quark_media 2>&1
        if ($LASTEXITCODE -eq 0) {
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
}

if ($elapsed -ge $timeout) {
    Write-Host "错误: PostgreSQL 启动超时" -ForegroundColor Red
    docker-compose logs postgres
    exit 1
}
Write-Host "✓ PostgreSQL 已就绪" -ForegroundColor Green

Write-Host "等待 Redis..." -ForegroundColor Cyan
$timeout = 30
$elapsed = 0
while ($elapsed -lt $timeout) {
    try {
        $result = docker-compose exec -T redis redis-cli ping 2>&1
        if ($result -match "PONG") {
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 1
    $elapsed += 1
}

if ($elapsed -ge $timeout) {
    Write-Host "错误: Redis 启动超时" -ForegroundColor Red
    docker-compose logs redis
    exit 1
}
Write-Host "✓ Redis 已就绪" -ForegroundColor Green

Write-Host "等待 WebDAV..." -ForegroundColor Cyan
$timeout = 60
$elapsed = 0
while ($elapsed -lt $timeout) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5244/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
}

if ($elapsed -ge $timeout) {
    Write-Host "警告: WebDAV 健康检查超时，但服务可能仍在启动" -ForegroundColor Yellow
} else {
    Write-Host "✓ WebDAV 已就绪" -ForegroundColor Green
}

Write-Host "等待后端 API..." -ForegroundColor Cyan
$timeout = 60
$elapsed = 0
while ($elapsed -lt $timeout) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
}

if ($elapsed -ge $timeout) {
    Write-Host "警告: 后端 API 健康检查超时，但服务可能仍在启动" -ForegroundColor Yellow
} else {
    Write-Host "✓ 后端 API 已就绪" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "服务访问地址:" -ForegroundColor Cyan
Write-Host "  - WebDAV:     http://localhost:5244" -ForegroundColor White
Write-Host "  - 后端 API:   http://localhost:8000" -ForegroundColor White
Write-Host "  - API 文档:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Redis:      localhost:6379" -ForegroundColor White
Write-Host "  - PostgreSQL: localhost:5432" -ForegroundColor White
Write-Host ""
Write-Host "常用命令:" -ForegroundColor Cyan
Write-Host "  查看日志:     docker-compose logs -f [service_name]" -ForegroundColor White
Write-Host "  停止服务:     docker-compose stop" -ForegroundColor White
Write-Host "  重启服务:     docker-compose restart" -ForegroundColor White
Write-Host "  完全清理:     docker-compose down -v" -ForegroundColor White
Write-Host ""
Write-Host "容器状态:" -ForegroundColor Cyan
docker-compose ps
Write-Host ""
