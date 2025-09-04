#!/usr/bin/env python3
"""
MinIO到Label Studio导入示例
演示如何处理包含多个文件夹（每个文件夹有.meta文件和WAV音频文件）的数据
"""

import os
import json
import yaml
from typing import Dict, List, Any
from minio import Minio
from label_studio_sdk import Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinIOLabelStudioImporter:
    """MinIO到Label Studio导入器"""
    
    def __init__(self, minio_config: Dict, ls_config: Dict):
        """
        初始化导入器
        
        Args:
            minio_config: MinIO配置
            ls_config: Label Studio配置
        """
        self.minio_config = minio_config
        self.ls_config = ls_config
        
        # 初始化MinIO客户端
        self.minio_client = Minio(
            minio_config["endpoint"],
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=minio_config["secure"]
        )
        
        # 初始化Label Studio客户端
        self.ls_client = Client(
            url=ls_config["url"],
            api_key=ls_config["api_key"]
        )
        
    def scan_minio_bucket(self, bucket_name: str, prefix: str = "") -> List[Dict]:
        """
        扫描MinIO bucket中的文件夹结构
        
        Args:
            bucket_name: 存储桶名称
            prefix: 前缀路径
            
        Returns:
            文件夹和文件列表
        """
        folders = {}
        
        try:
            objects = self.minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
            
            for obj in objects:
                # 解析对象路径
                path_parts = obj.object_name.split('/')
                
                if len(path_parts) >= 2:
                    folder_name = path_parts[0]
                    file_name = path_parts[1]
                    
                    if folder_name not in folders:
                        folders[folder_name] = {
                            'folder_name': folder_name,
                            'wav_files': [],
                            'meta_files': []
                        }
                    
                    # 分类文件
                    if file_name.endswith('.wav'):
                        folders[folder_name]['wav_files'].append({
                            'object_name': obj.object_name,
                            'file_name': file_name,
                            'size': obj.size,
                            'last_modified': obj.last_modified
                        })
                    elif file_name.endswith('.meta'):
                        folders[folder_name]['meta_files'].append({
                            'object_name': obj.object_name,
                            'file_name': file_name,
                            'size': obj.size,
                            'last_modified': obj.last_modified
                        })
            
            logger.info(f"扫描到 {len(folders)} 个文件夹")
            return list(folders.values())
            
        except Exception as e:
            logger.error(f"扫描MinIO bucket失败: {e}")
            return []
    
    def read_meta_file(self, bucket_name: str, object_name: str) -> Dict:
        """
        读取.meta文件内容
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称
            
        Returns:
            元数据字典
        """
        try:
            response = self.minio_client.get_object(bucket_name, object_name)
            meta_data = json.loads(response.read().decode('utf-8'))
            response.close()
            response.release_conn()
            return meta_data
        except Exception as e:
            logger.error(f"读取meta文件失败 {object_name}: {e}")
            return {}
    
    def download_file(self, bucket_name: str, object_name: str, local_path: str) -> bool:
        """
        下载文件到本地
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称
            local_path: 本地路径
            
        Returns:
            是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 下载文件
            self.minio_client.fget_object(bucket_name, object_name, local_path)
            logger.info(f"下载文件成功: {object_name} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"下载文件失败 {object_name}: {e}")
            return False
    
    def create_label_studio_task(self, wav_file: Dict, meta_data: Dict, folder_name: str) -> Dict:
        """
        创建Label Studio任务数据
        
        Args:
            wav_file: WAV文件信息
            meta_data: 元数据
            folder_name: 文件夹名称
            
        Returns:
            任务数据字典
        """
        # 构建本地文件路径
        local_wav_path = f"/data/upload/{folder_name}/{wav_file['file_name']}"
        local_meta_path = f"/data/upload/{folder_name}/{wav_file['file_name'].replace('.wav', '.meta')}"
        
        # 构建任务数据
        task_data = {
            "audio": local_wav_path,
            "audio_id": meta_data.get("audio_id", wav_file['file_name'].replace('.wav', '')),
            "folder": folder_name,
            "filename": wav_file['file_name'],
            "duration": meta_data.get("duration", 0),
            "sample_rate": meta_data.get("sample_rate", 44100),
            "channels": meta_data.get("channels", 2),
            "file_size": wav_file['size'],
            "upload_time": meta_data.get("upload_time", ""),
            "tags": meta_data.get("tags", []),
            "speaker_info": meta_data.get("speaker_info", {}),
            "recording_info": meta_data.get("recording_info", {}),
            "meta_file": local_meta_path
        }
        
        # 添加元信息
        meta_info = {
            "created_at": wav_file['last_modified'].isoformat(),
            "updated_at": wav_file['last_modified'].isoformat(),
            "imported_from": f"minio://{self.minio_config['bucket']}/{wav_file['object_name']}"
        }
        
        return {
            "data": task_data,
            "meta": meta_info
        }
    
    def import_to_label_studio(self, bucket_name: str, project_id: int, prefix: str = "") -> Dict:
        """
        导入数据到Label Studio
        
        Args:
            bucket_name: 存储桶名称
            project_id: Label Studio项目ID
            prefix: 前缀路径
            
        Returns:
            导入结果
        """
        try:
            # 扫描MinIO bucket
            folders = self.scan_minio_bucket(bucket_name, prefix)
            
            if not folders:
                return {"error": "未找到任何文件夹"}
            
            # 获取项目
            project = self.ls_client.get_project(project_id)
            
            tasks = []
            imported_count = 0
            failed_count = 0
            
            for folder in folders:
                folder_name = folder['folder_name']
                logger.info(f"处理文件夹: {folder_name}")
                
                # 创建本地文件夹
                local_folder_path = f"/data/upload/{folder_name}"
                os.makedirs(local_folder_path, exist_ok=True)
                
                # 处理WAV文件
                for wav_file in folder['wav_files']:
                    try:
                        # 查找对应的meta文件
                        meta_file_name = wav_file['file_name'].replace('.wav', '.meta')
                        meta_file = None
                        
                        for mf in folder['meta_files']:
                            if mf['file_name'] == meta_file_name:
                                meta_file = mf
                                break
                        
                        # 读取元数据
                        meta_data = {}
                        if meta_file:
                            meta_data = self.read_meta_file(bucket_name, meta_file['object_name'])
                        
                        # 下载WAV文件
                        local_wav_path = f"{local_folder_path}/{wav_file['file_name']}"
                        if self.download_file(bucket_name, wav_file['object_name'], local_wav_path):
                            # 创建任务数据
                            task = self.create_label_studio_task(wav_file, meta_data, folder_name)
                            tasks.append(task)
                            imported_count += 1
                            logger.info(f"成功处理: {wav_file['file_name']}")
                        else:
                            failed_count += 1
                            logger.error(f"下载失败: {wav_file['file_name']}")
                    
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"处理文件失败 {wav_file['file_name']}: {e}")
            
            # 批量导入到Label Studio
            if tasks:
                project.import_tasks(tasks)
                logger.info(f"成功导入 {len(tasks)} 个任务到Label Studio")
            
            return {
                "success": True,
                "imported_count": imported_count,
                "failed_count": failed_count,
                "total_folders": len(folders),
                "total_tasks": len(tasks)
            }
            
        except Exception as e:
            logger.error(f"导入到Label Studio失败: {e}")
            return {"error": str(e)}
    
    def export_annotations(self, project_id: int, export_format: str = "JSON") -> Dict:
        """
        导出标注数据
        
        Args:
            project_id: 项目ID
            export_format: 导出格式 (JSON, CSV, YOLO等)
            
        Returns:
            导出结果
        """
        try:
            project = self.ls_client.get_project(project_id)
            
            # 导出标注数据
            export_data = project.export_tasks(export_format)
            
            # 保存到文件
            output_file = f"annotations_export_{project_id}.{export_format.lower()}"
            with open(output_file, 'w', encoding='utf-8') as f:
                if export_format == "JSON":
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                else:
                    f.write(export_data)
            
            logger.info(f"标注数据已导出到: {output_file}")
            
            return {
                "success": True,
                "output_file": output_file,
                "export_format": export_format
            }
            
        except Exception as e:
            logger.error(f"导出标注数据失败: {e}")
            return {"error": str(e)}

def main():
    """主函数示例"""
    
    # 配置信息
    minio_config = {
        "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        "access_key": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        "secret_key": os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        "bucket": os.getenv("MINIO_BUCKET", "audio-storage"),
        "secure": os.getenv("MINIO_SECURE", "false").lower() == "true"
    }
    
    ls_config = {
        "url": os.getenv("LABEL_STUDIO_URL", "http://localhost:8080"),
        "api_key": os.getenv("LABEL_STUDIO_API_KEY", "your_api_key_here"),
        "username": os.getenv("LABEL_STUDIO_USERNAME", "admin"),
        "password": os.getenv("LABEL_STUDIO_PASSWORD", "admin123")
    }
    
    # 创建导入器
    importer = MinIOLabelStudioImporter(minio_config, ls_config)
    
    # 示例：扫描bucket
    print("=== 扫描MinIO Bucket ===")
    folders = importer.scan_minio_bucket(minio_config["bucket"])
    
    for folder in folders:
        print(f"文件夹: {folder['folder_name']}")
        print(f"  WAV文件: {len(folder['wav_files'])} 个")
        print(f"  Meta文件: {len(folder['meta_files'])} 个")
        
        for wav_file in folder['wav_files']:
            print(f"    - {wav_file['file_name']} ({wav_file['size']} bytes)")
    
    # 示例：导入到Label Studio
    print("\n=== 导入到Label Studio ===")
    project_id = 1  # 替换为实际的项目ID
    
    result = importer.import_to_label_studio(minio_config["bucket"], project_id)
    
    if result.get("success"):
        print(f"导入成功!")
        print(f"  导入任务数: {result['imported_count']}")
        print(f"  失败任务数: {result['failed_count']}")
        print(f"  总文件夹数: {result['total_folders']}")
    else:
        print(f"导入失败: {result.get('error')}")
    
    # 示例：导出标注数据
    print("\n=== 导出标注数据 ===")
    export_result = importer.export_annotations(project_id, "JSON")
    
    if export_result.get("success"):
        print(f"导出成功: {export_result['output_file']}")
    else:
        print(f"导出失败: {export_result.get('error')}")

if __name__ == "__main__":
    main()
