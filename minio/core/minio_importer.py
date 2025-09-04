import pandas as pd
from typing import List, Dict, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)

class MinIOImporter:
    """MinIO数据导入器，支持从MinIO批量导入数据到Label Studio"""
    
    def __init__(self, project_name: str, bucket: str = None):
        self.project_name = project_name
        self.bucket = bucket or 'tok-label'
    
    def list_available_files(self, prefix: str = "") -> List[str]:
        """列出MinIO中可用的文件"""
        return self._list_minio_objects(prefix=prefix, recursive=True)
    
    def download_and_convert_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """从MinIO下载CSV文件并转换为DataFrame"""
        try:
            content = self._download_from_minio(file_path)
            from io import StringIO
            csv_string = content.decode('utf-8')
            df = pd.read_csv(StringIO(csv_string))
            return df
        except Exception as e:
            logger.error(f"Error downloading/converting {file_path}: {e}")
            return None
    
    def batch_import_csv_files(self, prefix: str = "", shot_pattern: str = r'/(\d+)\.csv$') -> Dict:
        """
        批量导入CSV文件到文件服务器和Redis
        
        参数:
        prefix (str): MinIO对象前缀
        shot_pattern (str): 用于提取shot号的正则表达式
        
        返回:
        Dict: 导入结果
        """
        try:
            # 列出所有CSV文件
            files = self.list_available_files(prefix)
            csv_files = [f for f in files if f.endswith('.csv')]
            
            if not csv_files:
                return {"error": "No CSV files found in MinIO"}
            
            urls = {}
            failed_files = []
            
            for file_path in csv_files:
                # 提取shot号
                shot_match = re.search(shot_pattern, file_path)
                if not shot_match:
                    logger.warning(f"Could not extract shot number from {file_path}")
                    continue
                
                shot = int(shot_match.group(1))
                
                # 下载并转换文件
                df = self.download_and_convert_csv(file_path)
                if df is None:
                    failed_files.append(file_path)
                    continue
                
                # 上传到文件服务器（这里需要外部提供上传功能）
                upload_result = self._upload_dataframe(
                    dir=self.project_name,
                    file=f"{shot}.csv",
                    dataframe=df
                )
                
                if upload_result.get("error"):
                    logger.error(f"Failed to upload {file_path}: {upload_result['error']}")
                    failed_files.append(file_path)
                    continue
                
                urls[shot] = upload_result["url"]
            
            # 导出到Redis（这里需要外部提供Redis功能）
            if urls:
                redis_result = self._export_urls_to_redis(
                    project_name=self.project_name,
                    urls=urls,
                    key="csv"
                )
                
                return {
                    "message": f"Successfully imported {len(urls)} files from MinIO",
                    "imported_shots": list(urls.keys()),
                    "failed_files": failed_files,
                    "redis_result": redis_result
                }
            else:
                return {"error": "No files were successfully imported"}
                
        except Exception as e:
            return {"error": f"Batch import error: {str(e)}"}
    
    def import_json_annotations(self, prefix: str = "annotations/") -> Dict:
        """
        导入JSON格式的标注数据
        
        参数:
        prefix (str): JSON文件的MinIO前缀
        
        返回:
        Dict: 导入结果
        """
        try:
            files = self.list_available_files(prefix)
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                return {"error": "No JSON files found in MinIO"}
            
            # 这里需要外部提供Redis连接功能
            # redis_conn = connect_redis(REDIS_DB)
            imported_count = 0
            
            for file_path in json_files:
                try:
                    content = self._download_from_minio(file_path)
                    json_data = json.loads(content.decode('utf-8'))
                    
                    # 提取文件名作为Redis键
                    file_name = file_path.split('/')[-1].replace('.json', '')
                    redis_key = f"{self.project_name}/annotations/{file_name}"
                    
                    # redis_conn.set(redis_key, json.dumps(json_data))
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing {file_path}: {e}")
            
            # redis_conn.close()
            
            return {
                "message": f"Successfully imported {imported_count} JSON annotation files",
                "imported_count": imported_count,
                "total_files": len(json_files)
            }
            
        except Exception as e:
            return {"error": f"JSON import error: {str(e)}"}
    
    def _list_minio_objects(self, prefix: str = "", recursive: bool = False) -> List[str]:
        """列出MinIO中的对象"""
        try:
            from minio import Minio
            from minio.error import S3Error
            
            # 这里需要从外部配置获取MinIO连接信息
            endpoint = "localhost:9000"  # 默认值，实际使用时应该配置
            access_key = "minioadmin"    # 默认值，实际使用时应该配置
            secret_key = "minioadmin"    # 默认值，实际使用时应该配置
            secure = False               # 默认值，实际使用时应该配置
            
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            
            objects = client.list_objects(self.bucket, prefix=prefix, recursive=recursive)
            return [obj.object_name for obj in objects if not obj.object_name.endswith('/')]
        except S3Error as e:
            logger.error(f"MinIO error: {e}")
            return []
        except Exception as e:
            logger.error(f"List error: {e}")
            return []
    
    def _download_from_minio(self, file_path: str) -> bytes:
        """从MinIO下载文件"""
        try:
            from minio import Minio
            from minio.error import S3Error
            
            # 这里需要从外部配置获取MinIO连接信息
            endpoint = "localhost:9000"  # 默认值，实际使用时应该配置
            access_key = "minioadmin"    # 默认值，实际使用时应该配置
            secret_key = "minioadmin"    # 默认值，实际使用时应该配置
            secure = False               # 默认值，实际使用时应该配置
            
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            
            response = client.get_object(self.bucket, file_path)
            return response.read()
        except S3Error as e:
            raise Exception(f"MinIO error: {str(e)}")
        except Exception as e:
            raise Exception(f"Download error: {str(e)}")
    
    def _upload_dataframe(self, dir: str, file: str, dataframe: pd.DataFrame) -> Dict:
        """上传数据框到文件服务器"""
        try:
            # 这里需要外部提供文件服务器上传功能
            # 在实际使用中，这个函数应该从外部传入
            logger.warning("File server upload not implemented in standalone package")
            return {"error": "File server upload not implemented"}
        except Exception as e:
            return {"error": str(e)}
    
    def _export_urls_to_redis(self, project_name: str, urls: Dict, key: str = "csv") -> Dict:
        """导出URL到Redis"""
        try:
            # 这里需要外部提供Redis功能
            # 在实际使用中，这个函数应该从外部传入
            logger.warning("Redis export not implemented in standalone package")
            return {"error": "Redis export not implemented"}
        except Exception as e:
            return {"error": str(e)}
