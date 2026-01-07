# 数据库迁移指南

## 迁移说明

本次迁移为 `virtualmedia` 表添加以下字段：
- `retry_count`: 重试次数
- `error_message`: 错误信息
- `last_retry_at`: 最后重试时间
- `updated_at`: 更新时间

## 迁移步骤

### 1. 备份数据库

**Linux/Mac:**
```bash
python backup_db.py
```

**Windows (PowerShell):**
```powershell
.\backup_db.ps1
```

备份文件将保存在 `services/backups/` 目录下，文件名格式为 `quark_media_YYYYMMDD_HHMMSS.sql`

### 2. 执行迁移

迁移脚本位于 `services/alembic_versions.py`

**手动执行SQL:**
```sql
-- 添加新字段
ALTER TABLE virtualmedia ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE virtualmedia ADD COLUMN error_message VARCHAR;
ALTER TABLE virtualmedia ADD COLUMN last_retry_at TIMESTAMP;
ALTER TABLE virtualmedia ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();

-- 创建索引以提高查询性能
CREATE INDEX idx_virtualmedia_task_status ON virtualmedia(task_status);
CREATE INDEX idx_virtualmedia_retry_count ON virtualmedia(retry_count);
CREATE INDEX idx_virtualmedia_last_retry_at ON virtualmedia(last_retry_at);
```

**使用Alembic:**
```bash
cd services
alembic upgrade head
```

### 3. 验证迁移

连接到数据库验证字段是否添加成功：
```sql
\d virtualmedia
```

检查现有数据：
```sql
SELECT id, title, task_status, retry_count, error_message, last_retry_at, updated_at 
FROM virtualmedia 
LIMIT 10;
```

### 4. 恢复数据库（如需要）

**Linux/Mac:**
```bash
python backup_db.py restore backups/quark_media_YYYYMMDD_HHMMSS.sql
```

**Windows (PowerShell):**
```powershell
.\backup_db.ps1 restore backups\quark_media_YYYYMMDD_HHMMSS.sql
```

## 回滚方案

如果需要回滚迁移：
```sql
-- 删除索引
DROP INDEX IF EXISTS idx_virtualmedia_task_status;
DROP INDEX IF EXISTS idx_virtualmedia_retry_count;
DROP INDEX IF EXISTS idx_virtualmedia_last_retry_at;

-- 删除字段
ALTER TABLE virtualmedia DROP COLUMN IF EXISTS retry_count;
ALTER TABLE virtualmedia DROP COLUMN IF EXISTS error_message;
ALTER TABLE virtualmedia DROP COLUMN IF EXISTS last_retry_at;
ALTER TABLE virtualmedia DROP COLUMN IF EXISTS updated_at;
```

## 注意事项

1. **生产环境操作前务必备份数据库**
2. 建议在低峰期执行迁移
3. 迁移过程中可能短暂影响服务可用性
4. 确保有足够的磁盘空间存储备份文件
5. 备份文件建议保留至少30天

## 环境变量

确保以下环境变量已正确设置：
- `POSTGRES_HOST`: PostgreSQL主机地址
- `POSTGRES_PORT`: PostgreSQL端口
- `POSTGRES_DB`: 数据库名称
- `POSTGRES_USER`: 数据库用户名
- `POSTGRES_PASSWORD`: 数据库密码

## 故障排查

### 备份失败
- 检查PostgreSQL服务是否运行
- 验证数据库连接参数是否正确
- 确认有足够的磁盘空间

### 迁移失败
- 检查数据库用户权限
- 验证表名和字段名是否正确
- 查看PostgreSQL日志获取详细错误信息

### 恢复失败
- 确认备份文件存在且未损坏
- 验证数据库连接参数
- 检查目标数据库是否为空
