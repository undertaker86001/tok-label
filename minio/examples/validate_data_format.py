#!/usr/bin/env python3
"""
数据格式验证脚本
验证MinIO到Label Studio的数据格式是否正确
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

class DataFormatValidator:
    """数据格式验证器"""
    
    def __init__(self, minio_config: Dict, ls_config: Dict):
        """
        初始化验证器
        
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
    
    def validate_minio_structure(self, bucket_name: str, prefix: str = "") -> Dict:
        """
        验证MinIO中的数据结构
        
        Args:
            bucket_name: 存储桶名称
            prefix: 前缀路径
            
        Returns:
            验证结果
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "folders": [],
            "total_wav_files": 0,
            "total_meta_files": 0
        }
        
        try:
            # 检查bucket是否存在
            if not self.minio_client.bucket_exists(bucket_name):
                validation_result["valid"] = False
                validation_result["errors"].append(f"Bucket '{bucket_name}' 不存在")
                return validation_result
            
            # 扫描对象
            objects = list(self.minio_client.list_objects(bucket_name, prefix=prefix, recursive=True))
            
            if not objects:
                validation_result["warnings"].append("Bucket中没有找到任何文件")
                return validation_result
            
            # 分析文件夹结构
            folders = {}
            
            for obj in objects:
                path_parts = obj.object_name.split('/')
                
                if len(path_parts) >= 2:
                    folder_name = path_parts[0]
                    file_name = path_parts[1]
                    
                    if folder_name not in folders:
                        folders[folder_name] = {
                            'folder_name': folder_name,
                            'wav_files': [],
                            'meta_files': [],
                            'other_files': []
                        }
                    
                    # 分类文件
                    if file_name.endswith('.wav'):
                        folders[folder_name]['wav_files'].append({
                            'object_name': obj.object_name,
                            'file_name': file_name,
                            'size': obj.size
                        })
                        validation_result["total_wav_files"] += 1
                    elif file_name.endswith('.meta'):
                        folders[folder_name]['meta_files'].append({
                            'object_name': obj.object_name,
                            'file_name': file_name,
                            'size': obj.size
                        })
                        validation_result["total_meta_files"] += 1
                    else:
                        folders[folder_name]['other_files'].append({
                            'object_name': obj.object_name,
                            'file_name': file_name,
                            'size': obj.size
                        })
            
            validation_result["folders"] = list(folders.values())
            
            # 验证每个文件夹
            for folder in folders.values():
                folder_name = folder['folder_name']
                
                # 检查是否有WAV文件
                if not folder['wav_files']:
                    validation_result["warnings"].append(f"文件夹 '{folder_name}' 中没有WAV文件")
                
                # 检查是否有meta文件
                if not folder['meta_files']:
                    validation_result["warnings"].append(f"文件夹 '{folder_name}' 中没有meta文件")
                
                # 检查WAV文件和meta文件是否配对
                wav_names = {w['file_name'].replace('.wav', '') for w in folder['wav_files']}
                meta_names = {m['file_name'].replace('.meta', '') for m in folder['meta_files']}
                
                # 找到没有对应meta文件的WAV文件
                wav_without_meta = wav_names - meta_names
                if wav_without_meta:
                    validation_result["warnings"].append(f"文件夹 '{folder_name}' 中的WAV文件缺少对应的meta文件: {list(wav_without_meta)}")
                
                # 找到没有对应WAV文件的meta文件
                meta_without_wav = meta_names - wav_names
                if meta_without_wav:
                    validation_result["warnings"].append(f"文件夹 '{folder_name}' 中的meta文件缺少对应的WAV文件: {list(meta_without_wav)}")
                
                # 验证meta文件格式
                for meta_file in folder['meta_files']:
                    try:
                        response = self.minio_client.get_object(bucket_name, meta_file['object_name'])
                        meta_data = json.loads(response.read().decode('utf-8'))
                        response.close()
                        response.release_conn()
                        
                        # 验证必需的字段
                        required_fields = ['audio_id', 'filename', 'duration', 'sample_rate']
                        missing_fields = [field for field in required_fields if field not in meta_data]
                        
                        if missing_fields:
                            validation_result["warnings"].append(f"meta文件 '{meta_file['file_name']}' 缺少必需字段: {missing_fields}")
                        
                    except json.JSONDecodeError:
                        validation_result["errors"].append(f"meta文件 '{meta_file['file_name']}' 不是有效的JSON格式")
                    except Exception as e:
                        validation_result["errors"].append(f"读取meta文件 '{meta_file['file_name']}' 失败: {e}")
            
            return validation_result
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"验证MinIO结构失败: {e}")
            return validation_result
    
    def validate_label_studio_tasks(self, project_id: int) -> Dict:
        """
        验证Label Studio中的任务数据格式
        
        Args:
            project_id: 项目ID
            
        Returns:
            验证结果
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "total_tasks": 0,
            "total_annotations": 0,
            "task_samples": []
        }
        
        try:
            # 获取项目
            project = self.ls_client.get_project(project_id)
            
            # 获取任务列表
            tasks = project.get_tasks()
            validation_result["total_tasks"] = len(tasks)
            
            if not tasks:
                validation_result["warnings"].append("项目中没有任务")
                return validation_result
            
            # 验证每个任务
            for i, task in enumerate(tasks[:5]):  # 只验证前5个任务作为样本
                task_validation = self._validate_single_task(task)
                
                if not task_validation["valid"]:
                    validation_result["valid"] = False
                    validation_result["errors"].extend(task_validation["errors"])
                
                validation_result["warnings"].extend(task_validation["warnings"])
                validation_result["task_samples"].append(task_validation["task_sample"])
                
                # 统计标注数量
                validation_result["total_annotations"] += len(task.get("annotations", []))
            
            return validation_result
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"验证Label Studio任务失败: {e}")
            return validation_result
    
    def _validate_single_task(self, task: Dict) -> Dict:
        """
        验证单个任务的数据格式
        
        Args:
            task: 任务数据
            
        Returns:
            验证结果
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "task_sample": {}
        }
        
        try:
            task_id = task.get("id")
            data = task.get("data", {})
            annotations = task.get("annotations", [])
            meta = task.get("meta", {})
            
            # 保存任务样本
            validation_result["task_sample"] = {
                "id": task_id,
                "data_keys": list(data.keys()),
                "annotation_count": len(annotations),
                "meta_keys": list(meta.keys())
            }
            
            # 验证必需的数据字段
            required_data_fields = ["audio", "audio_id", "folder", "filename"]
            missing_data_fields = [field for field in required_data_fields if field not in data]
            
            if missing_data_fields:
                validation_result["errors"].append(f"任务 {task_id} 缺少必需的数据字段: {missing_data_fields}")
            
            # 验证音频文件路径
            audio_path = data.get("audio", "")
            if not audio_path:
                validation_result["errors"].append(f"任务 {task_id} 缺少音频文件路径")
            elif not audio_path.endswith('.wav'):
                validation_result["warnings"].append(f"任务 {task_id} 的音频文件路径可能不是WAV格式: {audio_path}")
            
            # 验证元数据字段
            if "duration" in data and not isinstance(data["duration"], (int, float)):
                validation_result["warnings"].append(f"任务 {task_id} 的duration字段不是数字类型")
            
            if "sample_rate" in data and not isinstance(data["sample_rate"], int):
                validation_result["warnings"].append(f"任务 {task_id} 的sample_rate字段不是整数类型")
            
            # 验证标注数据
            for i, annotation in enumerate(annotations):
                if not isinstance(annotation, dict):
                    validation_result["errors"].append(f"任务 {task_id} 的标注 {i} 不是字典格式")
                    continue
                
                result = annotation.get("result", [])
                if not isinstance(result, list):
                    validation_result["errors"].append(f"任务 {task_id} 的标注 {i} 的result字段不是列表格式")
                    continue
                
                for j, result_item in enumerate(result):
                    if not isinstance(result_item, dict):
                        validation_result["errors"].append(f"任务 {task_id} 的标注 {i} 的result项 {j} 不是字典格式")
                        continue
                    
                    # 验证result项的基本字段
                    required_result_fields = ["id", "type", "value", "from_name", "to_name"]
                    missing_result_fields = [field for field in required_result_fields if field not in result_item]
                    
                    if missing_result_fields:
                        validation_result["warnings"].append(f"任务 {task_id} 的标注 {i} 的result项 {j} 缺少字段: {missing_result_fields}")
            
            return validation_result
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"验证任务失败: {e}")
            return validation_result
    
    def compare_minio_and_labelstudio(self, bucket_name: str, project_id: int) -> Dict:
        """
        比较MinIO和Label Studio中的数据一致性
        
        Args:
            bucket_name: 存储桶名称
            project_id: 项目ID
            
        Returns:
            比较结果
        """
        comparison_result = {
            "consistent": True,
            "errors": [],
            "warnings": [],
            "minio_files": [],
            "ls_tasks": [],
            "missing_in_ls": [],
            "missing_in_minio": []
        }
        
        try:
            # 获取MinIO中的文件列表
            minio_files = []
            objects = self.minio_client.list_objects(bucket_name, recursive=True)
            
            for obj in objects:
                if obj.object_name.endswith('.wav'):
                    minio_files.append({
                        'object_name': obj.object_name,
                        'file_name': obj.object_name.split('/')[-1],
                        'folder': obj.object_name.split('/')[0] if '/' in obj.object_name else '',
                        'size': obj.size
                    })
            
            comparison_result["minio_files"] = minio_files
            
            # 获取Label Studio中的任务列表
            project = self.ls_client.get_project(project_id)
            tasks = project.get_tasks()
            
            ls_tasks = []
            for task in tasks:
                data = task.get("data", {})
                ls_tasks.append({
                    'task_id': task.get("id"),
                    'audio_path': data.get("audio", ""),
                    'audio_id': data.get("audio_id", ""),
                    'folder': data.get("folder", ""),
                    'filename': data.get("filename", "")
                })
            
            comparison_result["ls_tasks"] = ls_tasks
            
            # 比较文件数量
            if len(minio_files) != len(ls_tasks):
                comparison_result["consistent"] = False
                comparison_result["warnings"].append(f"文件数量不一致: MinIO中有 {len(minio_files)} 个WAV文件，Label Studio中有 {len(ls_tasks)} 个任务")
            
            # 检查MinIO中有但Label Studio中没有的文件
            minio_file_names = {f['file_name'] for f in minio_files}
            ls_file_names = {t['filename'] for t in ls_tasks}
            
            missing_in_ls = minio_file_names - ls_file_names
            if missing_in_ls:
                comparison_result["consistent"] = False
                comparison_result["missing_in_ls"] = list(missing_in_ls)
                comparison_result["warnings"].append(f"Label Studio中缺少 {len(missing_in_ls)} 个文件")
            
            # 检查Label Studio中有但MinIO中没有的文件
            missing_in_minio = ls_file_names - minio_file_names
            if missing_in_minio:
                comparison_result["warnings"].append(f"MinIO中缺少 {len(missing_in_minio)} 个文件")
                comparison_result["missing_in_minio"] = list(missing_in_minio)
            
            return comparison_result
            
        except Exception as e:
            comparison_result["consistent"] = False
            comparison_result["errors"].append(f"比较MinIO和Label Studio数据失败: {e}")
            return comparison_result

def main():
    """主函数"""
    
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
        "api_key": os.getenv("LABEL_STUDIO_API_KEY", "your_api_key_here")
    }
    
    # 创建验证器
    validator = DataFormatValidator(minio_config, ls_config)
    
    print("=== MinIO数据结构验证 ===")
    minio_result = validator.validate_minio_structure(minio_config["bucket"])
    
    print(f"验证结果: {'通过' if minio_result['valid'] else '失败'}")
    print(f"文件夹数量: {len(minio_result['folders'])}")
    print(f"WAV文件总数: {minio_result['total_wav_files']}")
    print(f"Meta文件总数: {minio_result['total_meta_files']}")
    
    if minio_result['errors']:
        print("\n错误:")
        for error in minio_result['errors']:
            print(f"  - {error}")
    
    if minio_result['warnings']:
        print("\n警告:")
        for warning in minio_result['warnings']:
            print(f"  - {warning}")
    
    print("\n=== Label Studio任务数据验证 ===")
    project_id = 1  # 替换为实际的项目ID
    
    ls_result = validator.validate_label_studio_tasks(project_id)
    
    print(f"验证结果: {'通过' if ls_result['valid'] else '失败'}")
    print(f"任务总数: {ls_result['total_tasks']}")
    print(f"标注总数: {ls_result['total_annotations']}")
    
    if ls_result['errors']:
        print("\n错误:")
        for error in ls_result['errors']:
            print(f"  - {error}")
    
    if ls_result['warnings']:
        print("\n警告:")
        for warning in ls_result['warnings']:
            print(f"  - {warning}")
    
    print("\n=== 数据一致性比较 ===")
    comparison_result = validator.compare_minio_and_labelstudio(minio_config["bucket"], project_id)
    
    print(f"一致性: {'是' if comparison_result['consistent'] else '否'}")
    
    if comparison_result['missing_in_ls']:
        print(f"Label Studio中缺少的文件: {len(comparison_result['missing_in_ls'])}")
        for file_name in comparison_result['missing_in_ls'][:5]:  # 只显示前5个
            print(f"  - {file_name}")
    
    if comparison_result['missing_in_minio']:
        print(f"MinIO中缺少的文件: {len(comparison_result['missing_in_minio'])}")
        for file_name in comparison_result['missing_in_minio'][:5]:  # 只显示前5个
            print(f"  - {file_name}")
    
    if comparison_result['errors']:
        print("\n错误:")
        for error in comparison_result['errors']:
            print(f"  - {error}")
    
    if comparison_result['warnings']:
        print("\n警告:")
        for warning in comparison_result['warnings']:
            print(f"  - {warning}")

if __name__ == "__main__":
    main()
