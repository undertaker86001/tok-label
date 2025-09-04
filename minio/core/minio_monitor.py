import time
import logging
from typing import Dict, List, Optional
from .utils import list_minio_objects, download_from_minio
from .config import MINIO_BUCKET, MINIO_ENDPOINT
from minio import Minio
from minio.error import S3Error
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MinIOMonitor:
    """MinIO监控器，提供健康检查和数据监控功能"""
    
    def __init__(self, bucket: str = None):
        self.bucket = bucket or MINIO_BUCKET
        self.client = None
        self._initialize_client()
        
    def _initialize_client(self):
        """初始化MinIO客户端"""
        try:
            from .config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE
            self.client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE
            )
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
    
    def health_check(self) -> Dict:
        """MinIO健康检查"""
        try:
            if not self.client:
                return {"status": "error", "message": "MinIO client not initialized"}
            
            # 检查连接
            buckets = self.client.list_buckets()
            
            # 检查目标桶是否存在
            bucket_exists = self.client.bucket_exists(self.bucket)
            
            # 获取桶信息
            bucket_info = None
            if bucket_exists:
                objects = list(self.client.list_objects(self.bucket, recursive=False))
                bucket_info = {
                    "object_count": len(objects),
                    "bucket_name": self.bucket
                }
            
            return {
                "status": "healthy",
                "endpoint": MINIO_ENDPOINT,
                "bucket_exists": bucket_exists,
                "bucket_info": bucket_info,
                "total_buckets": len(buckets),
                "timestamp": datetime.now().isoformat()
            }
            
        except S3Error as e:
            return {
                "status": "error",
                "message": f"MinIO S3 error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"MinIO connection error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_storage_statistics(self, prefix: str = "") -> Dict:
        """获取存储统计信息"""
        try:
            if not self.client:
                return {"error": "MinIO client not initialized"}
            
            objects = list(self.client.list_objects(self.bucket, prefix=prefix, recursive=True))
            
            # 统计信息
            total_objects = len(objects)
            total_size = sum(obj.size for obj in objects if obj.size)
            
            # 按文件类型分组
            file_types = {}
            for obj in objects:
                ext = obj.object_name.split('.')[-1].lower() if '.' in obj.object_name else 'no_ext'
                if ext not in file_types:
                    file_types[ext] = {"count": 0, "size": 0}
                file_types[ext]["count"] += 1
                file_types[ext]["size"] += obj.size if obj.size else 0
            
            # 最近修改的文件
            recent_objects = sorted(objects, key=lambda x: x.last_modified, reverse=True)[:10]
            recent_files = [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat()
                }
                for obj in recent_objects
            ]
            
            return {
                "total_objects": total_objects,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": file_types,
                "recent_files": recent_files,
                "bucket": self.bucket,
                "prefix": prefix
            }
            
        except Exception as e:
            return {"error": f"Failed to get storage statistics: {str(e)}"}
    
    def monitor_data_changes(self, prefix: str = "", check_interval: int = 60) -> None:
        """监控数据变化（后台运行）"""
        def monitor_loop():
            last_object_list = set()
            
            while True:
                try:
                    current_objects = set(list_minio_objects(prefix=prefix, bucket=self.bucket, recursive=True))
                    
                    # 检查新增文件
                    new_objects = current_objects - last_object_list
                    if new_objects:
                        logger.info(f"New objects detected: {list(new_objects)}")
                    
                    # 检查删除文件
                    deleted_objects = last_object_list - current_objects
                    if deleted_objects:
                        logger.info(f"Deleted objects detected: {list(deleted_objects)}")
                    
                    last_object_list = current_objects
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                    time.sleep(check_interval)
        
        # 在后台线程中运行监控
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info(f"Started MinIO monitor for prefix '{prefix}' with {check_interval}s interval")
