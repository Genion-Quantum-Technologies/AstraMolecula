#!/usr/bin/env python3
"""
历史数据迁移脚本
将本地文件系统中的文件迁移到 SeaweedFS

使用方法：
    python migrate_to_seaweedfs.py --dry-run  # 仅预览，不实际迁移
    python migrate_to_seaweedfs.py --uploads  # 迁移用户上传文件
    python migrate_to_seaweedfs.py --jobs     # 迁移任务文件
    python migrate_to_seaweedfs.py --all      # 迁移全部
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ROOT
from database.db import get_connection
from services.storage import get_storage


class MigrationStats:
    """迁移统计"""
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
    
    def report(self):
        print("\n" + "=" * 50)
        print("迁移统计")
        print("=" * 50)
        print(f"总数: {self.total}")
        print(f"成功: {self.success}")
        print(f"失败: {self.failed}")
        print(f"跳过: {self.skipped}")
        if self.errors:
            print("\n失败详情:")
            for err in self.errors[:10]:  # 只显示前10个错误
                print(f"  - {err}")
            if len(self.errors) > 10:
                print(f"  ... 还有 {len(self.errors) - 10} 个错误")


async def migrate_uploads(dry_run: bool = True):
    """迁移用户上传文件"""
    print("\n正在迁移用户上传文件...")
    stats = MigrationStats()
    storage = get_storage()
    
    # 获取所有上传记录
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("""
                SELECT id, user_id, filename, file_path 
                FROM user_uploads 
                WHERE file_path LIKE '/%'
            """)
            uploads = cur.fetchall()
    finally:
        conn.close()
    
    stats.total = len(uploads)
    print(f"找到 {stats.total} 个需要迁移的上传记录")
    
    for upload in uploads:
        local_path = Path(upload['file_path'])
        remote_key = f"uploads/{upload['user_id']}/{upload['filename']}"
        
        if not local_path.exists():
            print(f"  [跳过] {local_path} 文件不存在")
            stats.skipped += 1
            continue
        
        if await storage.file_exists(remote_key):
            print(f"  [跳过] {remote_key} 已存在于 SeaweedFS")
            stats.skipped += 1
            continue
        
        if dry_run:
            print(f"  [预览] {local_path} -> {remote_key}")
            stats.success += 1
        else:
            try:
                # 上传文件
                await storage.upload_file(local_path, remote_key)
                
                # 获取文件信息
                file_size = local_path.stat().st_size
                
                # 更新数据库记录
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE user_uploads 
                            SET file_path = %s, file_size = %s
                            WHERE id = %s
                        """, (remote_key, file_size, upload['id']))
                    conn.commit()
                finally:
                    conn.close()
                
                print(f"  [成功] {local_path} -> {remote_key}")
                stats.success += 1
            except Exception as e:
                print(f"  [失败] {local_path}: {e}")
                stats.failed += 1
                stats.errors.append(f"{upload['id']}: {e}")
    
    return stats


async def migrate_jobs(dry_run: bool = True):
    """迁移任务文件"""
    print("\n正在迁移任务文件...")
    stats = MigrationStats()
    storage = get_storage()
    
    jobs_dir = ROOT / "jobs"
    if not jobs_dir.exists():
        print("jobs 目录不存在，跳过")
        return stats
    
    # 遍历所有任务类型
    for task_type_dir in jobs_dir.iterdir():
        if not task_type_dir.is_dir():
            continue
        
        task_type = task_type_dir.name
        print(f"\n处理 {task_type} 任务...")
        
        # 遍历所有任务
        for job_dir in task_type_dir.iterdir():
            if not job_dir.is_dir():
                continue
            
            job_id = job_dir.name
            storage_prefix = f"jobs/{task_type}/{job_id}"
            
            # 遍历任务目录下的所有文件
            for file_path in job_dir.rglob('*'):
                if not file_path.is_file():
                    continue
                
                stats.total += 1
                relative_path = file_path.relative_to(job_dir)
                remote_key = f"{storage_prefix}/{relative_path}"
                
                if await storage.file_exists(remote_key):
                    stats.skipped += 1
                    continue
                
                if dry_run:
                    print(f"  [预览] {file_path} -> {remote_key}")
                    stats.success += 1
                else:
                    try:
                        await storage.upload_file(file_path, remote_key)
                        print(f"  [成功] {file_path} -> {remote_key}")
                        stats.success += 1
                    except Exception as e:
                        print(f"  [失败] {file_path}: {e}")
                        stats.failed += 1
                        stats.errors.append(f"{remote_key}: {e}")
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description='将本地文件迁移到 SeaweedFS')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际迁移')
    parser.add_argument('--uploads', action='store_true', help='迁移用户上传文件')
    parser.add_argument('--jobs', action='store_true', help='迁移任务文件')
    parser.add_argument('--all', action='store_true', help='迁移全部')
    
    args = parser.parse_args()
    
    if not any([args.uploads, args.jobs, args.all]):
        parser.print_help()
        return
    
    print("=" * 50)
    print("SeaweedFS 数据迁移工具")
    print("=" * 50)
    print(f"时间: {datetime.now().isoformat()}")
    print(f"模式: {'预览' if args.dry_run else '实际迁移'}")
    print()
    
    all_stats = MigrationStats()
    
    if args.uploads or args.all:
        stats = await migrate_uploads(args.dry_run)
        all_stats.total += stats.total
        all_stats.success += stats.success
        all_stats.failed += stats.failed
        all_stats.skipped += stats.skipped
        all_stats.errors.extend(stats.errors)
    
    if args.jobs or args.all:
        stats = await migrate_jobs(args.dry_run)
        all_stats.total += stats.total
        all_stats.success += stats.success
        all_stats.failed += stats.failed
        all_stats.skipped += stats.skipped
        all_stats.errors.extend(stats.errors)
    
    all_stats.report()
    
    if args.dry_run:
        print("\n这是预览模式，没有实际迁移文件。")
        print("使用不带 --dry-run 参数运行以执行实际迁移。")


if __name__ == '__main__':
    asyncio.run(main())
