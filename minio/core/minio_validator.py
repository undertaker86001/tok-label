import pandas as pd
from typing import Dict, List, Optional, Tuple
from .minio_importer import MinIOImporter
from .utils import download_from_minio
import logging
import json

logger = logging.getLogger(__name__)

class MinIODataValidator:
    """MinIO数据验证器，验证数据完整性和格式正确性"""
    
    def __init__(self, project_name: str, bucket: str = None):
        self.project_name = project_name
        self.importer = MinIOImporter(project_name, bucket)
        
    def validate_csv_files(self, prefix: str = "", required_columns: List[str] = None) -> Dict:
        """
        验证CSV文件格式和内容
        
        参数:
        prefix: MinIO对象前缀
        required_columns: 必需的列名列表
        
        返回:
        Dict: 验证结果
        """
        try:
            files = self.importer.list_available_files(prefix)
            csv_files = [f for f in files if f.endswith('.csv')]
            
            if not csv_files:
                return {"error": "No CSV files found for validation"}
            
            validation_results = []
            valid_files = []
            invalid_files = []
            
            for file_path in csv_files:
                file_result = {
                    "file": file_path,
                    "valid": True,
                    "issues": []
                }
                
                try:
                    # 下载并解析CSV
                    df = self.importer.download_and_convert_csv(file_path)
                    if df is None:
                        file_result["valid"] = False
                        file_result["issues"].append("Failed to parse CSV")
                        invalid_files.append(file_path)
                        validation_results.append(file_result)
                        continue
                    
                    # 检查必需列
                    if required_columns:
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        if missing_columns:
                            file_result["valid"] = False
                            file_result["issues"].append(f"Missing columns: {missing_columns}")
                    
                    # 检查数据完整性
                    if df.empty:
                        file_result["valid"] = False
                        file_result["issues"].append("Empty DataFrame")
                    
                    # 检查数据类型
                    if 'time' in df.columns:
                        if not pd.api.types.is_numeric_dtype(df['time']):
                            file_result["issues"].append("Time column is not numeric")
                    
                    # 检查重复值
                    if df.duplicated().any():
                        file_result["issues"].append("Contains duplicate rows")
                    
                    # 检查缺失值
                    missing_data = df.isnull().sum()
                    if missing_data.any():
                        file_result["issues"].append(f"Missing values: {missing_data.to_dict()}")
                    
                    file_result["row_count"] = len(df)
                    file_result["column_count"] = len(df.columns)
                    file_result["columns"] = list(df.columns)
                    
                    if file_result["valid"]:
                        valid_files.append(file_path)
                    else:
                        invalid_files.append(file_path)
                    
                except Exception as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"Validation error: {str(e)}")
                    invalid_files.append(file_path)
                
                validation_results.append(file_result)
            
            return {
                "message": f"Validated {len(csv_files)} CSV files",
                "total_files": len(csv_files),
                "valid_files": len(valid_files),
                "invalid_files": len(invalid_files),
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {"error": f"Validation error: {str(e)}"}
    
    def validate_data_consistency(self, shots: List[int], prefix: str = "") -> Dict:
        """
        验证多个shot数据的一致性
        
        参数:
        shots: 炮号列表
        prefix: MinIO对象前缀
        
        返回:
        Dict: 一致性验证结果
        """
        try:
            consistency_issues = []
            shot_data = {}
            
            # 加载所有shot数据
            for shot in shots:
                file_path = f"{prefix}/{self.project_name}/{shot}.csv" if prefix else f"{self.project_name}/{shot}.csv"
                df = self.importer.download_and_convert_csv(file_path)
                if df is not None:
                    shot_data[shot] = df
                else:
                    consistency_issues.append(f"Failed to load data for shot {shot}")
            
            if not shot_data:
                return {"error": "No valid shot data found"}
            
            # 检查列一致性
            all_columns = [set(df.columns) for df in shot_data.values()]
            if len(set(frozenset(cols) for cols in all_columns)) > 1:
                consistency_issues.append("Inconsistent column names across shots")
            
            # 检查时间范围一致性
            time_ranges = {}
            for shot, df in shot_data.items():
                if 'time' in df.columns:
                    time_ranges[shot] = {
                        "min": df['time'].min(),
                        "max": df['time'].max(),
                        "count": len(df)
                    }
            
            # 检查时间范围差异
            if time_ranges:
                min_times = [tr["min"] for tr in time_ranges.values()]
                max_times = [tr["max"] for tr in time_ranges.values()]
                counts = [tr["count"] for tr in time_ranges.values()]
                
                if max(min_times) - min(min_times) > 0.1:  # 100ms差异
                    consistency_issues.append("Significant time range start differences")
                
                if max(max_times) - min(max_times) > 0.1:  # 100ms差异
                    consistency_issues.append("Significant time range end differences")
                
                if max(counts) - min(counts) > len(shot_data) * 0.1:  # 10%差异
                    consistency_issues.append("Significant data point count differences")
            
            return {
                "message": f"Validated consistency for {len(shot_data)} shots",
                "shots_validated": list(shot_data.keys()),
                "consistency_issues": consistency_issues,
                "time_ranges": time_ranges,
                "is_consistent": len(consistency_issues) == 0
            }
            
        except Exception as e:
            return {"error": f"Consistency validation error: {str(e)}"}
    
    def validate_annotation_files(self, prefix: str = "annotations/") -> Dict:
        """
        验证标注文件的格式和内容
        
        参数:
        prefix: 标注文件的MinIO前缀
        
        返回:
        Dict: 验证结果
        """
        try:
            files = self.importer.list_available_files(prefix)
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                return {"error": "No JSON annotation files found"}
            
            validation_results = []
            valid_annotations = []
            invalid_annotations = []
            
            for file_path in json_files:
                file_result = {
                    "file": file_path,
                    "valid": True,
                    "issues": [],
                    "annotation_count": 0
                }
                
                try:
                    content = download_from_minio(file_path, self.importer.bucket)
                    annotation_data = json.loads(content.decode('utf-8'))
                    
                    # 检查JSON结构
                    if not isinstance(annotation_data, (list, dict)):
                        file_result["valid"] = False
                        file_result["issues"].append("Invalid JSON structure")
                    
                    # 如果是列表，检查每个标注
                    if isinstance(annotation_data, list):
                        file_result["annotation_count"] = len(annotation_data)
                        
                        for i, annotation in enumerate(annotation_data):
                            if not isinstance(annotation, dict):
                                file_result["issues"].append(f"Annotation {i} is not a dictionary")
                                continue
                            
                            # 检查必需字段
                            required_fields = ['id', 'result']
                            missing_fields = [field for field in required_fields if field not in annotation]
                            if missing_fields:
                                file_result["issues"].append(f"Annotation {i} missing fields: {missing_fields}")
                    
                    elif isinstance(annotation_data, dict):
                        file_result["annotation_count"] = 1
                        
                        # 检查单个标注的结构
                        if 'annotations' in annotation_data:
                            file_result["annotation_count"] = len(annotation_data['annotations'])
                    
                    if file_result["issues"]:
                        file_result["valid"] = False
                        invalid_annotations.append(file_path)
                    else:
                        valid_annotations.append(file_path)
                    
                except json.JSONDecodeError as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"JSON decode error: {str(e)}")
                    invalid_annotations.append(file_path)
                except Exception as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"Validation error: {str(e)}")
                    invalid_annotations.append(file_path)
                
                validation_results.append(file_result)
            
            return {
                "message": f"Validated {len(json_files)} annotation files",
                "total_files": len(json_files),
                "valid_files": len(valid_annotations),
                "invalid_files": len(invalid_annotations),
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {"error": f"Annotation validation error: {str(e)}"}
