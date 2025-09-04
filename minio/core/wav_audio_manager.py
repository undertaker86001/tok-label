"""
WAV音频文件管理器
支持WAV文件的MinIO存储、Label Studio集成和标注数据管理
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from minio import Minio
from label_studio_sdk import Client

logger = logging.getLogger(__name__)

class WAVAudioManager:
    """WAV音频文件管理器，专门处理音频标注场景"""
    
    def __init__(self, minio_client: Minio, bucket_name: str):
        self.minio_client = minio_client
        self.bucket_name = bucket_name
        
    def upload_wav_file(self, local_path: str, minio_path: str) -> Dict:
        """上传WAV文件到MinIO"""
        try:
            if not os.path.exists(local_path):
                return {"error": f"File not found: {local_path}"}
            
            # 检查文件是否为WAV格式
            if not local_path.lower().endswith('.wav'):
                return {"error": "File must be in WAV format"}
            
            # 上传到MinIO
            self.minio_client.fput_object(
                self.bucket_name, 
                minio_path, 
                local_path,
                content_type="audio/wav"
            )
            
            # 生成预签名URL
            url = self.minio_client.presigned_get_object(
                self.bucket_name, 
                minio_path, 
                expires=3600  # 1小时有效期
            )
            
            return {
                "success": True,
                "minio_path": minio_path,
                "url": url,
                "file_size": os.path.getsize(local_path)
            }
            
        except Exception as e:
            return {"error": f"Upload failed: {str(e)}"}
    
    def create_label_studio_task(self, wav_url: str, metadata: Dict = None) -> Dict:
        """创建Label Studio任务格式的WAV文件任务"""
        task = {
            "data": {
                "audio": wav_url,
                "audio_type": "wav"
            }
        }
        
        if metadata:
            task["meta"] = metadata
            
        return task
    
    def create_audio_annotation_config(self) -> str:
        """创建音频标注的Label Studio配置"""
        config = """
<View>
  <Header value="音频标注任务"/>
  <Audio name="audio" value="$audio" hotkey="space" zoom="true" height="400"/>
  <Labels name="label" toName="audio">
    <Label value="正常" background="green"/>
    <Label value="异常" background="red"/>
    <Label value="噪音" background="orange"/>
    <Label value="静音" background="gray"/>
  </Labels>
  <TextArea name="notes" toName="audio" 
            perRegion="true" 
            displayMode="region-list" 
            placeholder="请输入标注说明..."/>
  <Choices name="quality" toName="audio">
    <Choice value="高质量"/>
    <Choice value="中等质量"/>
    <Choice value="低质量"/>
  </Choices>
</View>
        """
        return config.strip()
    
    def create_timeseries_audio_config(self) -> str:
        """创建时间序列音频标注配置"""
        config = """
<View>
  <Header value="时间序列音频标注"/>
  <Audio name="audio" value="$audio" hotkey="space" zoom="true" height="400"/>
  <TimeSeriesLabels name="label" toName="audio">
    <Label value="语音开始" background="green"/>
    <Label value="语音结束" background="red"/>
    <Label value="噪音段" background="orange"/>
    <Label value="静音段" background="gray"/>
  </TimeSeriesLabels>
  <TextArea name="transcription" toName="audio" 
            perRegion="true" 
            displayMode="region-list" 
            placeholder="请输入转写文本..."/>
</View>
        """
        return config.strip()
    
    def batch_upload_wav_files(self, local_dir: str, minio_prefix: str) -> List[Dict]:
        """批量上传WAV文件"""
        results = []
        
        try:
            for filename in os.listdir(local_dir):
                if filename.lower().endswith('.wav'):
                    local_path = os.path.join(local_dir, filename)
                    minio_path = f"{minio_prefix}/{filename}"
                    
                    result = self.upload_wav_file(local_path, minio_path)
                    result["filename"] = filename
                    results.append(result)
                    
        except Exception as e:
            results.append({"error": f"Batch upload failed: {str(e)}"})
            
        return results
    
    def create_audio_project_tasks(self, wav_files: List[Dict], 
                                 project_metadata: Dict = None) -> List[Dict]:
        """创建音频项目的Label Studio任务列表"""
        tasks = []
        
        for wav_file in wav_files:
            if wav_file.get("success"):
                task = self.create_label_studio_task(
                    wav_file["url"],
                    {
                        "filename": wav_file["filename"],
                        "file_size": wav_file["file_size"],
                        "upload_time": datetime.now().isoformat(),
                        **project_metadata or {}
                    }
                )
                tasks.append(task)
                
        return tasks
    
    def export_audio_annotations(self, ls_client: Client, project_id: int) -> Dict:
        """导出音频标注数据"""
        try:
            # 导出标注数据
            annotations = ls_client.get_project(project_id).export_annotations()
            
            # 处理音频标注数据
            processed_annotations = []
            
            for annotation in annotations:
                processed_annotation = {
                    "task_id": annotation.get("id"),
                    "audio_url": annotation.get("data", {}).get("audio"),
                    "annotations": []
                }
                
                # 处理标注结果
                for result in annotation.get("annotations", []):
                    for res in result.get("result", []):
                        if res.get("type") == "labels":
                            processed_annotation["annotations"].append({
                                "type": "label",
                                "value": res.get("value", {}).get("labels", []),
                                "start": res.get("value", {}).get("start"),
                                "end": res.get("value", {}).get("end")
                            })
                        elif res.get("type") == "textarea":
                            processed_annotation["annotations"].append({
                                "type": "text",
                                "value": res.get("value", {}).get("text", ""),
                                "start": res.get("value", {}).get("start"),
                                "end": res.get("value", {}).get("end")
                            })
                        elif res.get("type") == "choices":
                            processed_annotation["annotations"].append({
                                "type": "choice",
                                "value": res.get("value", {}).get("choices", [])
                            })
                
                processed_annotations.append(processed_annotation)
            
            return {
                "success": True,
                "annotations": processed_annotations,
                "total_count": len(processed_annotations)
            }
            
        except Exception as e:
            return {"error": f"Export failed: {str(e)}"}
    
    def save_annotations_to_postgres(self, annotations: List[Dict], 
                                   db_connection) -> Dict:
        """将标注数据保存到PostgreSQL"""
        try:
            # 创建标注表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS audio_annotations (
                id SERIAL PRIMARY KEY,
                task_id INTEGER,
                audio_url TEXT,
                annotation_type VARCHAR(50),
                annotation_value TEXT,
                start_time FLOAT,
                end_time FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            with db_connection.cursor() as cursor:
                cursor.execute(create_table_sql)
                
                # 插入标注数据
                for annotation in annotations:
                    for ann in annotation.get("annotations", []):
                        insert_sql = """
                        INSERT INTO audio_annotations 
                        (task_id, audio_url, annotation_type, annotation_value, start_time, end_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        
                        cursor.execute(insert_sql, (
                            annotation["task_id"],
                            annotation["audio_url"],
                            ann["type"],
                            json.dumps(ann["value"]) if isinstance(ann["value"], (list, dict)) else str(ann["value"]),
                            ann.get("start"),
                            ann.get("end")
                        ))
                
                db_connection.commit()
            
            return {
                "success": True,
                "message": f"Saved {len(annotations)} annotations to PostgreSQL"
            }
            
        except Exception as e:
            return {"error": f"Database save failed: {str(e)}"}
    
    def restore_annotations_from_postgres(self, task_id: int, 
                                        db_connection) -> Dict:
        """从PostgreSQL恢复标注数据"""
        try:
            select_sql = """
            SELECT * FROM audio_annotations 
            WHERE task_id = %s 
            ORDER BY start_time, created_at
            """
            
            with db_connection.cursor() as cursor:
                cursor.execute(select_sql, (task_id,))
                rows = cursor.fetchall()
            
            annotations = []
            for row in rows:
                annotations.append({
                    "type": row[3],  # annotation_type
                    "value": json.loads(row[4]) if row[4].startswith('[') or row[4].startswith('{') else row[4],  # annotation_value
                    "start": row[5],  # start_time
                    "end": row[6]     # end_time
                })
            
            return {
                "success": True,
                "task_id": task_id,
                "annotations": annotations
            }
            
        except Exception as e:
            return {"error": f"Database restore failed: {str(e)}"}
    
    def create_audio_workflow_config(self) -> Dict:
        """创建音频工作流配置"""
        return {
            "audio_processing": {
                "supported_formats": ["wav"],
                "max_file_size_mb": 100,
                "sample_rate": 44100,
                "channels": 2
            },
            "annotation_types": {
                "label": "标签标注",
                "timeseries": "时间序列标注",
                "transcription": "文本转写"
            },
            "storage": {
                "minio_bucket": self.bucket_name,
                "audio_prefix": "audio_files/",
                "annotations_prefix": "annotations/"
            }
        }
