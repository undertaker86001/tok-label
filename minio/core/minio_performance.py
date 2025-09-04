import time
import asyncio
import aiohttp
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import upload_to_minio, download_from_minio
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MinIOPerformanceOptimizer:
    """MinIO性能优化器，提供并发上传下载和缓存功能"""
    
    def __init__(self, bucket: str = None, max_workers: int = 20):
        self.bucket = bucket
        self.max_workers = max_workers
        self.cache = {}
        
    def parallel_upload_dataframes(self, data_dict: Dict[str, pd.DataFrame], prefix: str = "") -> Dict:
        """
        并行上传多个DataFrame到MinIO
        
        参数:
        data_dict: {file_path: DataFrame} 字典
        prefix: MinIO对象前缀
        
        返回:
        Dict: 上传结果
        """
        def upload_single_df(item):
            file_path, df = item
            full_path = f"{prefix}/{file_path}" if prefix else file_path
            csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
            
            start_time = time.time()
            result = upload_to_minio(full_path, csv_content, self.bucket)
            upload_time = time.time() - start_time
            
            return {
                "file_path": full_path,
                "result": result,
                "upload_time": upload_time,
                "size": len(csv_content)
            }
        
        start_total = time.time()
        uploaded_files = []
        failed_files = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(upload_single_df, item): item for item in data_dict.items()}
            
            for future in as_completed(future_to_item):
                result = future.result()
                
                if result["result"].get("error"):
                    failed_files.append({
                        "file_path": result["file_path"],
                        "error": result["result"]["error"]
                    })
                else:
                    uploaded_files.append(result)
        
        total_time = time.time() - start_total
        total_size = sum(f["size"] for f in uploaded_files)
        
        return {
            "message": f"Parallel upload completed: {len(uploaded_files)} success, {len(failed_files)} failed",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "performance": {
                "total_time": total_time,
                "total_size_mb": total_size / (1024 * 1024),
                "average_speed_mbps": (total_size / (1024 * 1024)) / total_time if total_time > 0 else 0
            }
        }
    
    def parallel_download_dataframes(self, file_paths: List[str], use_cache: bool = True) -> Dict:
        """
        并行下载多个文件并转换为DataFrame
        
        参数:
        file_paths: 文件路径列表
        use_cache: 是否使用缓存
        
        返回:
        Dict: 下载结果
        """
        def download_single_file(file_path):
            # 检查缓存
            if use_cache and file_path in self.cache:
                return {
                    "file_path": file_path,
                    "dataframe": self.cache[file_path],
                    "from_cache": True,
                    "download_time": 0
                }
            
            start_time = time.time()
            try:
                content = download_from_minio(file_path, self.bucket)
                from io import StringIO
                csv_string = content.decode('utf-8')
                df = pd.read_csv(StringIO(csv_string))
                
                # 添加到缓存
                if use_cache:
                    self.cache[file_path] = df
                
                download_time = time.time() - start_time
                
                return {
                    "file_path": file_path,
                    "dataframe": df,
                    "from_cache": False,
                    "download_time": download_time,
                    "size": len(content)
                }
                
            except Exception as e:
                return {
                    "file_path": file_path,
                    "error": str(e),
                    "download_time": time.time() - start_time
                }
        
        start_total = time.time()
        downloaded_data = {}
        failed_downloads = []
        cache_hits = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {executor.submit(download_single_file, path): path for path in file_paths}
            
            for future in as_completed(future_to_path):
                result = future.result()
                
                if "error" in result:
                    failed_downloads.append(result)
                else:
                    downloaded_data[result["file_path"]] = result["dataframe"]
                    if result["from_cache"]:
                        cache_hits += 1
        
        total_time = time.time() - start_total
        
        return {
            "message": f"Parallel download completed: {len(downloaded_data)} success, {len(failed_downloads)} failed",
            "downloaded_data": downloaded_data,
            "failed_downloads": failed_downloads,
            "performance": {
                "total_time": total_time,
                "cache_hits": cache_hits,
                "cache_hit_rate": cache_hits / len(file_paths) if file_paths else 0
            }
        }
    
    def clear_cache(self):
        """清理缓存"""
        self.cache.clear()
        logger.info("MinIO performance cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        total_memory = sum(df.memory_usage(deep=True).sum() for df in self.cache.values())
        
        return {
            "cached_files": len(self.cache),
            "total_memory_mb": total_memory / (1024 * 1024),
            "cached_file_paths": list(self.cache.keys())
        }
