import os
import subprocess
import datetime
import time
import anyio
from ..core.config import settings

class BackupService:
    async def run_backup(self) -> dict:
        """
        Executes pg_dump on the Supabase PostgreSQL database.
        Saves the file to local backups directory and attempts to upload to S3 if configured.
        """
        try:
            db_password = os.environ.get("DB_PASSWORD", "Bytelytic@2025")
            db_host = os.environ.get("DB_HOST", "db.aabbhuzlzjkosqmvhysm.supabase.co")
            db_user = os.environ.get("DB_USER", "postgres")
            db_name = os.environ.get("DB_NAME", "postgres")
            db_port = os.environ.get("DB_PORT", "5432")
            
            # Directory to store backups in the root folder of the backend project
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            backup_dir = os.path.join(backend_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"db_backup_{timestamp}.sql"
            backup_filepath = os.path.join(backup_dir, backup_filename)
            
            # Set password in environment for pg_dump
            env = os.environ.copy()
            env["PGPASSWORD"] = db_password
            
            # Run pg_dump command (schema + data)
            cmd = [
                "pg_dump",
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                "-d", db_name,
                "-F", "c", # custom directory/archive format, highly compressed
                "-f", backup_filepath
            ]
            
            print(f"[BackupService] Starting pg_dump to {backup_filepath}...")
            
            def _run_dump():
                try:
                    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                    if result.returncode == 0:
                        return True, None
                    else:
                        return False, f"pg_dump error: {result.stderr}"
                except FileNotFoundError:
                    if settings.is_prod:
                        return False, "pg_dump utility not found on PATH. Backup failed in production."
                    with open(backup_filepath, "w") as f:
                        f.write(f"-- Bytelytic Clinic OS - Simulated DB Backup\n")
                        f.write(f"-- Timestamp: {timestamp}\n")
                        f.write(f"-- Warning: pg_dump utility was not found on PATH. Simulated fallback written.\n")
                    return True, "pg_dump utility not found on PATH. Simulated backup created."
            
            success, msg = await anyio.to_thread.run_sync(_run_dump)
            if not success:
                raise Exception(msg)
                
            print(f"[BackupService] Backup file generated successfully: {backup_filepath}")
            if msg:
                print(f"[BackupService] {msg}")
                
            # Attempt to upload to S3 if configured
            s3_bucket = os.environ.get("BACKUP_S3_BUCKET")
            aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            
            uploaded_to_s3 = False
            if s3_bucket and aws_access_key and aws_secret_key:
                try:
                    import boto3
                    s3 = boto3.client(
                        's3',
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key
                    )
                    await anyio.to_thread.run_sync(
                        lambda: s3.upload_file(backup_filepath, s3_bucket, f"database_backups/{backup_filename}")
                    )
                    print(f"[BackupService] Backup uploaded to S3 bucket {s3_bucket} successfully.")
                    uploaded_to_s3 = True
                except ImportError:
                    print("[BackupService] WARNING: boto3 package not installed. Skipping S3 upload.")
                except Exception as s3_err:
                    print(f"[BackupService] S3 Upload Failed: {s3_err}")
            else:
                print("[BackupService] S3 credentials or bucket not configured. Backup kept locally.")
                
            # Clean up old backups (keep only last 7 days)
            now_time = time.time()
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if os.path.isfile(filepath):
                    # check age in seconds (7 days = 604800s)
                    if os.stat(filepath).st_mtime < now_time - 604800:
                        os.remove(filepath)
                        print(f"[BackupService] Cleaned up old local backup: {filename}")
                        
            return {
                "success": True,
                "filepath": backup_filepath,
                "filename": backup_filename,
                "uploaded_to_s3": uploaded_to_s3,
                "message": msg or "Backup completed successfully."
            }
            
        except Exception as e:
            print(f"[BackupService.error] Backup failed: {str(e)}")
            return {"success": False, "error": str(e)}

backup_service = BackupService()
