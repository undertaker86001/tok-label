#!/usr/bin/env python3
"""
数据迁移工具：从本地存储迁移到MinIO
"""

import os
import argparse
import pandas as pd
from pathlib import Path
from typing import List, Dict
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_local_files_to_minio(local_data_dir: str, minio_prefix: str = "", bucket: str = "tok-label") -> Dict:
    """
    将本地文件迁移到MinIO
    
    参数:
    local_data_dir: 本地数据目录
    minio_prefix: MinIO对象前缀
    bucket: 目标存储桶
    
    返回:
    Dict: 迁移结果
    """
    try:
        from toklabel.utils import upload_to_minio
        
        local_path = Path(local_data_dir)
        if not local_path.exists():
            return {"error": f"Local directory {local_data_dir} does not exist"}
        
        migrated_files = []
        failed_files = []
        
        # 递归查找所有文件
        for file_path in local_path.rglob('*'):
            if file_path.is_file():
                try:
                    # 计算相对路径
                    rel_path = file_path.relative_to(local_path)
                    minio_path = f"{minio_prefix}/{rel_path}" if minio_prefix else str(rel_path)
                    minio_path = minio_path.replace('\\', '/')  # 确保使用正斜杠
                    
                    # 读取文件内容
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # 上传到MinIO
                    result = upload_to_minio(minio_path, content, bucket)
                    
                    if result.get("error"):
                        failed_files.append({
                            "local_path": str(file_path),
                            "minio_path": minio_path,
                            "error": result["error"]
                        })
                    else:
                        migrated_files.append({
                            "local_path": str(file_path),
                            "minio_path": minio_path,
                            "size": len(content)
                        })
                        logger.info(f"Migrated: {rel_path} -> {minio_path}")
                    
                except Exception as e:
                    failed_files.append({
                        "local_path": str(file_path),
                        "error": str(e)
                    })
        
        return {
            "message": f"Migration completed: {len(migrated_files)} files migrated, {len(failed_files)} failed",
            "migrated_files": migrated_files,
            "failed_files": failed_files,
            "total_size": sum(f["size"] for f in migrated_files)
        }
        
    except Exception as e:
        return {"error": f"Migration error: {str(e)}"}

def migrate_redis_urls_to_minio(project_name: str, redis_key: str = "csv", bucket: str = "tok-label") -> Dict:
    """
    将Redis中的URL数据迁移到MinIO
    
    参数:
    project_name: 项目名称
    redis_key: Redis键名
    bucket: 目标存储桶
    
    返回:
    Dict: 迁移结果
    """
    try:
        from toklabel.utils import connect_redis, upload_to_minio
        import requests
        
        # 连接Redis
        redis_conn = connect_redis()
        redis_data_key = f"{project_name}/{redis_key}"
        
        # 获取Redis中的URL数据
        urls_data = redis_conn.get(redis_data_key)
        if not urls_data:
            return {"error": f"No data found in Redis for key: {redis_data_key}"}
        
        import json
        urls = json.loads(urls_data)
        
        migrated_shots = []
        failed_shots = []
        
        for shot, url in urls.items():
            try:
                # 下载文件内容
                response = requests.get(url)
                response.raise_for_status()
                content = response.content
                
                # 上传到MinIO
                minio_path = f"{project_name}/data/{shot}.csv"
                result = upload_to_minio(minio_path, content, bucket)
                
                if result.get("error"):
                    failed_shots.append({
                        "shot": shot,
                        "url": url,
                        "error": result["error"]
                    })
                else:
                    migrated_shots.append({
                        "shot": shot,
                        "original_url": url,
                        "minio_path": minio_path
                    })
                    logger.info(f"Migrated shot {shot} to MinIO")
                
            except Exception as e:
                failed_shots.append({
                    "shot": shot,
                    "url": url,
                    "error": str(e)
                })
        
        redis_conn.close()
        
        return {
            "message": f"Redis migration completed: {len(migrated_shots)} shots migrated, {len(failed_shots)} failed",
            "migrated_shots": migrated_shots,
            "failed_shots": failed_shots
        }
        
    except Exception as e:
        return {"error": f"Redis migration error: {str(e)}"}

def main():
    parser = argparse.ArgumentParser(description='数据迁移到MinIO')
    parser.add_argument('--local-dir', help='本地数据目录路径')
    parser.add_argument('--project', help='项目名称（用于Redis迁移）')
    parser.add_argument('--redis-key', default='csv', help='Redis键名')
    parser.add_argument('--bucket', default='tok-label', help='MinIO存储桶')
    parser.add_argument('--prefix', default='', help='MinIO对象前缀')
    parser.add_argument('--mode', choices=['local', 'redis', 'both'], default='both', help='迁移模式')
    
    args = parser.parse_args()
    
    print("=== MinIO数据迁移工具 ===")
    
    results = {}
    
    # 本地文件迁移
    if args.mode in ['local', 'both'] and args.local_dir:
        print(f"\n开始迁移本地目录: {args.local_dir}")
        local_result = migrate_local_files_to_minio(
            args.local_dir, 
            args.prefix, 
            args.bucket
        )
        results['local_migration'] = local_result
        print("本地迁移结果:", json.dumps(local_result, indent=2, ensure_ascii=False))
    
    # Redis数据迁移
    if args.mode in ['redis', 'both'] and args.project:
        print(f"\n开始迁移Redis项目: {args.project}")
        redis_result = migrate_redis_urls_to_minio(
            args.project,
            args.redis_key,
            args.bucket
        )
        results['redis_migration'] = redis_result
        print("Redis迁移结果:", json.dumps(redis_result, indent=2, ensure_ascii=False))
    
    # 输出总结
    print("\n=== 迁移完成 ===")
    total_migrated = 0
    total_failed = 0
    
    for migration_type, result in results.items():
        if not result.get("error"):
            if migration_type == 'local_migration':
                total_migrated += len(result.get("migrated_files", []))
                total_failed += len(result.get("failed_files", []))
            elif migration_type == 'redis_migration':
                total_migrated += len(result.get("migrated_shots", []))
                total_failed += len(result.get("failed_shots", []))
    
    print(f"总计迁移成功: {total_migrated} 个文件")
    print(f"总计迁移失败: {total_failed} 个文件")

if __name__ == "__main__":
    main()
