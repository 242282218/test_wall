import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def backup_database():
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "quark_media")
    db_user = os.getenv("POSTGRES_USER", "quark")
    db_password = os.getenv("POSTGRES_PASSWORD", "quark_password")
    
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"quark_media_{timestamp}.sql"
    
    env = os.environ.copy()
    env["PGPASSWORD"] = db_password
    
    print(f"开始备份数据库: {db_name}")
    print(f"备份文件: {backup_file}")
    
    try:
        result = subprocess.run(
            [
                "pg_dump",
                f"--host={db_host}",
                f"--port={db_port}",
                f"--username={db_user}",
                f"--dbname={db_name}",
                "--no-password",
                "--verbose",
                "--format=plain",
                "--no-owner",
                "--no-acl"
            ],
            capture_output=True,
            text=True,
            env=env,
            check=True
        )
        
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        
        print(f"备份成功! 文件大小: {backup_file.stat().st_size / 1024:.2f} KB")
        return str(backup_file)
    
    except subprocess.CalledProcessError as e:
        print(f"备份失败: {e}")
        print(f"错误输出: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"备份过程中发生错误: {e}")
        sys.exit(1)

def restore_database(backup_file: str):
    if not Path(backup_file).exists():
        print(f"备份文件不存在: {backup_file}")
        sys.exit(1)
    
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "quark_media")
    db_user = os.getenv("POSTGRES_USER", "quark")
    db_password = os.getenv("POSTGRES_PASSWORD", "quark_password")
    
    env = os.environ.copy()
    env["PGPASSWORD"] = db_password
    
    print(f"开始恢复数据库: {db_name}")
    print(f"备份文件: {backup_file}")
    
    try:
        with open(backup_file, "r", encoding="utf-8") as f:
            result = subprocess.run(
                [
                    "psql",
                    f"--host={db_host}",
                    f"--port={db_port}",
                    f"--username={db_user}",
                    f"--dbname={db_name}",
                    "--no-password",
                    "--quiet"
                ],
                stdin=f,
                capture_output=True,
                text=True,
                env=env,
                check=True
            )
        
        print("恢复成功!")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"恢复失败: {e}")
        print(f"错误输出: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"恢复过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("用法: python backup_db.py restore <backup_file>")
            sys.exit(1)
        restore_database(sys.argv[2])
    else:
        backup_file = backup_database()
        print(f"\n如需恢复，请运行: python backup_db.py restore {backup_file}")
