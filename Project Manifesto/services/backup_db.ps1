$ErrorActionPreference = "Stop"

$dbHost = $env:POSTGRES_HOST
if (-not $dbHost) { $dbHost = "postgres" }

$dbPort = $env:POSTGRES_PORT
if (-not $dbPort) { $dbPort = "5432" }

$dbName = $env:POSTGRES_DB
if (-not $dbName) { $dbName = "quark_media" }

$dbUser = $env:POSTGRES_USER
if (-not $dbUser) { $dbUser = "quark" }

$dbPassword = $env:POSTGRES_PASSWORD
if (-not $dbPassword) { $dbPassword = "quark_password" }

$backupDir = "backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $backupDir "quark_media_$timestamp.sql"

$env:PGPASSWORD = $dbPassword

Write-Host "开始备份数据库: $dbName" -ForegroundColor Green
Write-Host "备份文件: $backupFile" -ForegroundColor Yellow

try {
    & pg_dump `
        --host=$dbHost `
        --port=$dbPort `
        --username=$dbUser `
        --dbname=$dbName `
        --no-password `
        --verbose `
        --format=plain `
        --no-owner `
        --no-acl `
        --file=$backupFile
    
    if ($LASTEXITCODE -eq 0) {
        $fileSize = (Get-Item $backupFile).Length / 1KB
        Write-Host "备份成功! 文件大小: $([math]::Round($fileSize, 2)) KB" -ForegroundColor Green
        Write-Host "`n如需恢复，请运行: .\backup_db.ps1 restore $backupFile" -ForegroundColor Cyan
    } else {
        Write-Host "备份失败，退出码: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "备份过程中发生错误: $_" -ForegroundColor Red
    exit 1
}

if ($args.Count -gt 0 -and $args[0] -eq "restore") {
    if ($args.Count -lt 2) {
        Write-Host "用法: .\backup_db.ps1 restore <backup_file>" -ForegroundColor Yellow
        exit 1
    }
    
    $restoreFile = $args[1]
    if (-not (Test-Path $restoreFile)) {
        Write-Host "备份文件不存在: $restoreFile" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "开始恢复数据库: $dbName" -ForegroundColor Green
    Write-Host "备份文件: $restoreFile" -ForegroundColor Yellow
    
    try {
        & psql `
            --host=$dbHost `
            --port=$dbPort `
            --username=$dbUser `
            --dbname=$dbName `
            --no-password `
            --quiet `
            --file=$restoreFile
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "恢复成功!" -ForegroundColor Green
        } else {
            Write-Host "恢复失败，退出码: $LASTEXITCODE" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "恢复过程中发生错误: $_" -ForegroundColor Red
        exit 1
    }
}
