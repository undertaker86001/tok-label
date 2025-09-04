import pandas as pd
from typing import List, Dict, Optional, Callable, Any
from .minio_importer import MinIOImporter
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

class MinIODataManager:
    """高级MinIO数据管理器，提供数据同步、转换和管理功能"""
    
    def __init__(self, project_name: str, bucket: str = None, config_module=None):
        self.project_name = project_name
        self.bucket = bucket or self._get_default_bucket(config_module)
        self.importer = MinIOImporter(project_name, bucket)
        
    def _get_default_bucket(self, config_module):
        """获取默认存储桶名称"""
        if config_module:
            return getattr(config_module, 'MINIO_BUCKET', 'tok-label')
        return 'tok-label'
        
    def batch_process_and_upload(
        self, 
        data_processor: Callable[[int], Optional[pd.DataFrame]], 
        shots: List[int],
        prefix: str = "",
        max_workers: int = 10,
        retry_failed: bool = True
    ) -> Dict:
        """
        批量处理数据并上传到MinIO
        
        参数:
        data_processor: 数据处理函数，接收shot号，返回DataFrame或None
        shots: 炮号列表
        prefix: MinIO对象前缀
        max_workers: 最大并发数
        retry_failed: 是否重试失败的任务
        
        返回:
        Dict: 处理结果
        """
        uploaded_files = []
        failed_files = []
        
        def process_single_shot(shot: int) -> Dict:
            try:
                # 处理数据
                df = data_processor(shot)
                if df is None:
                    return {"shot": shot, "status": "skipped", "reason": "No data returned"}
                
                # 上传到MinIO
                file_path = f"{prefix}/{self.project_name}/{shot}.csv" if prefix else f"{self.project_name}/{shot}.csv"
                csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
                
                result = self._upload_to_minio(file_path, csv_content)
                
                if result.get("error"):
                    return {"shot": shot, "status": "failed", "error": result["error"]}
                else:
                    return {"shot": shot, "status": "success", "path": file_path}
                    
            except Exception as e:
                return {"shot": shot, "status": "failed", "error": str(e)}
        
        # 并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_shot = {executor.submit(process_single_shot, shot): shot for shot in shots}
            
            for future in as_completed(future_to_shot):
                result = future.result()
                
                if result["status"] == "success":
                    uploaded_files.append(result)
                elif result["status"] == "failed":
                    failed_files.append(result)
                else:  # skipped
                    logger.info(f"Skipped shot {result['shot']}: {result['reason']}")
        
        # 重试失败的任务
        if retry_failed and failed_files:
            logger.info(f"Retrying {len(failed_files)} failed uploads...")
            retry_shots = [item["shot"] for item in failed_files]
            failed_files.clear()
            
            # 重试一次
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_shot = {executor.submit(process_single_shot, shot): shot for shot in retry_shots}
                
                for future in as_completed(future_to_shot):
                    result = future.result()
                    
                    if result["status"] == "success":
                        uploaded_files.append(result)
                    elif result["status"] == "failed":
                        failed_files.append(result)
        
        return {
            "message": f"Processed {len(shots)} shots, uploaded {len(uploaded_files)}, failed {len(failed_files)}",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "total_processed": len(shots)
        }
    
    def _upload_to_minio(self, file_path: str, content: bytes) -> Dict:
        """上传文件到MinIO"""
        try:
            from minio import Minio
            from minio.error import S3Error
            
            # 这里需要从外部配置获取MinIO连接信息
            # 在实际使用中，这些应该通过参数传入或从配置文件读取
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
            
            # 确保存储桶存在
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)
            
            # 上传文件
            from io import BytesIO
            client.put_object(
                self.bucket,
                file_path,
                BytesIO(content),
                len(content)
            )
            
            return {
                "message": f"File {file_path} uploaded to MinIO successfully",
                "path": file_path,
                "bucket": self.bucket
            }
        except S3Error as e:
            return {"error": f"MinIO error: {str(e)}"}
        except Exception as e:
            return {"error": f"Upload error: {str(e)}"}
    
    def sync_annotations_from_labelstudio(self, project_id: int, prefix: str = "annotations/", ls_config=None) -> Dict:
        """
        从Label Studio同步标注数据到MinIO
        
        参数:
        project_id: Label Studio项目ID
        prefix: MinIO存储前缀
        ls_config: Label Studio配置
        
        返回:
        Dict: 同步结果
        """
        try:
            from label_studio_sdk import Client
            
            # 获取Label Studio配置
            if ls_config:
                url = ls_config.get('url', 'http://localhost:8080')
                api_key = ls_config.get('api_key')
            else:
                url = 'http://localhost:8080'  # 默认值
                api_key = None  # 需要从外部传入
            
            if not api_key:
                return {"error": "Label Studio API key is required"}
            
            # 连接Label Studio
            ls = Client(url=url, api_key=api_key)
            project = ls.get_project(project_id)
            
            # 获取所有标注任务
            tasks = project.get_tasks()
            
            uploaded_annotations = []
            failed_annotations = []
            
            for task in tasks:
                try:
                    # 提取shot号
                    shot = task.get('data', {}).get('shot')
                    if not shot:
                        continue
                    
                    # 获取标注数据
                    annotations = task.get('annotations', [])
                    if not annotations:
                        continue
                    
                    # 上传到MinIO
                    file_path = f"{prefix}/{self.project_name}/{shot}.json"
                    json_content = json.dumps(annotations, ensure_ascii=False, indent=2).encode('utf-8')
                    
                    result = self._upload_to_minio(file_path, json_content)
                    
                    if result.get("error"):
                        failed_annotations.append({"shot": shot, "error": result["error"]})
                    else:
                        uploaded_annotations.append({"shot": shot, "path": file_path})
                        
                except Exception as e:
                    logger.error(f"Error processing task {task.get('id')}: {e}")
                    failed_annotations.append({"task_id": task.get('id'), "error": str(e)})
            
            return {
                "message": f"Synced {len(uploaded_annotations)} annotations from Label Studio",
                "uploaded_annotations": uploaded_annotations,
                "failed_annotations": failed_annotations
            }
            
        except Exception as e:
            return {"error": f"Label Studio sync error: {str(e)}"}
    
    def create_data_pipeline(self, pipeline_config: Dict) -> Dict:
        """
        创建数据处理管道
        
        参数:
        pipeline_config: 管道配置
        {
            "source": {"type": "postgres", "config": {...}},
            "processors": [{"type": "filter", "config": {...}}, ...],
            "destination": {"type": "minio", "prefix": "..."}
        }
        
        返回:
        Dict: 管道执行结果
        """
        try:
            source_config = pipeline_config.get("source", {})
            processors = pipeline_config.get("processors", [])
            destination = pipeline_config.get("destination", {})
            
            # 数据源处理
            if source_config.get("type") == "postgres":
                data_loader = self._create_postgres_loader(source_config.get("config", {}))
            elif source_config.get("type") == "minio":
                data_loader = self._create_minio_loader(source_config.get("config", {}))
            else:
                return {"error": f"Unsupported source type: {source_config.get('type')}"}
            
            # 数据处理器链
            processor_chain = []
            for proc_config in processors:
                processor = self._create_processor(proc_config)
                if processor:
                    processor_chain.append(processor)
            
            # 执行管道
            def pipeline_processor(shot: int) -> Optional[pd.DataFrame]:
                try:
                    # 加载数据
                    df = data_loader(shot)
                    if df is None:
                        return None
                    
                    # 应用处理器链
                    for processor in processor_chain:
                        df = processor(df)
                        if df is None:
                            return None
                    
                    return df
                    
                except Exception as e:
                    logger.error(f"Pipeline error for shot {shot}: {e}")
                    return None
            
            # 获取要处理的shots
            shots = source_config.get("config", {}).get("shots", [])
            if not shots:
                return {"error": "No shots specified in source config"}
            
            # 执行批量处理
            result = self.batch_process_and_upload(
                data_processor=pipeline_processor,
                shots=shots,
                prefix=destination.get("prefix", ""),
                max_workers=pipeline_config.get("max_workers", 10)
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Pipeline creation error: {str(e)}"}
    
    def _create_postgres_loader(self, config: Dict) -> Callable[[int], Optional[pd.DataFrame]]:
        """创建PostgreSQL数据加载器"""
        def postgres_loader(shot: int) -> Optional[pd.DataFrame]:
            try:
                # 这里需要外部提供PostgreSQL数据加载功能
                # 在实际使用中，这个函数应该从外部传入
                logger.warning("PostgreSQL loader not implemented in standalone package")
                return None
                
            except Exception as e:
                logger.error(f"PostgreSQL loader error for shot {shot}: {e}")
                return None
        
        return postgres_loader
    
    def _create_minio_loader(self, config: Dict) -> Callable[[int], Optional[pd.DataFrame]]:
        """创建MinIO数据加载器"""
        def minio_loader(shot: int) -> Optional[pd.DataFrame]:
            try:
                prefix = config.get("prefix", "")
                file_path = f"{prefix}/{shot}.csv"
                
                return self.importer.download_and_convert_csv(file_path)
                
            except Exception as e:
                logger.error(f"MinIO loader error for shot {shot}: {e}")
                return None
        
        return minio_loader
    
    def _create_processor(self, proc_config: Dict) -> Optional[Callable[[pd.DataFrame], Optional[pd.DataFrame]]]:
        """创建数据处理器"""
        proc_type = proc_config.get("type")
        config = proc_config.get("config", {})
        
        if proc_type == "filter":
            def filter_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    condition = config.get("condition")
                    if condition:
                        # 简单的条件过滤，可以扩展为更复杂的表达式
                        return df.query(condition)
                    return df
                except Exception as e:
                    logger.error(f"Filter processor error: {e}")
                    return None
            return filter_processor
        
        elif proc_type == "resample":
            def resample_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    time_column = config.get("time_column", "time")
                    frequency = config.get("frequency", "1ms")
                    
                    df_resampled = df.set_index(time_column).resample(frequency).mean()
                    return df_resampled.reset_index()
                except Exception as e:
                    logger.error(f"Resample processor error: {e}")
                    return None
            return resample_processor
        
        elif proc_type == "normalize":
            def normalize_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    columns = config.get("columns", [])
                    method = config.get("method", "minmax")
                    
                    df_normalized = df.copy()
                    for col in columns:
                        if col in df.columns:
                            if method == "minmax":
                                min_val = df[col].min()
                                max_val = df[col].max()
                                df_normalized[col] = (df[col] - min_val) / (max_val - min_val)
                            elif method == "zscore":
                                mean_val = df[col].mean()
                                std_val = df[col].std()
                                df_normalized[col] = (df[col] - mean_val) / std_val
                    
                    return df_normalized
                except Exception as e:
                    logger.error(f"Normalize processor error: {e}")
                    return None
            return normalize_processor
        
        else:
            logger.warning(f"Unknown processor type: {proc_type}")
            return None
