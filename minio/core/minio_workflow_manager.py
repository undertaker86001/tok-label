import logging
from typing import Dict, List, Optional
from .projectbuilder import ProjectBuilder
from .minio_data_manager import MinIODataManager
from .minio_config_manager import MinIOConfigManager
from .utils import export_annotation, simple_json_convertor
from .annotationmanage import AnnotationManager

logger = logging.getLogger(__name__)

class MinIOWorkflowManager:
    """MinIO集成工作流管理器，提供完整的数据处理和标注工作流"""
    
    def __init__(self, config_file: str):
        self.config_manager = MinIOConfigManager(config_file)
        self.project_builder = None
        self.data_manager = None
        
    def initialize_project(self, **kwargs) -> Dict:
        """初始化项目"""
        try:
            # 创建ProjectBuilder实例
            self.project_builder = ProjectBuilder(self.config_manager.config_file, **kwargs)
            
            # 创建数据管理器
            self.data_manager = MinIODataManager(
                self.project_builder.project,
                self.project_builder.minio_bucket
            )
            
            return {
                "message": "Project initialized successfully",
                "project_name": self.project_builder.project,
                "minio_enabled": self.project_builder.minio_enabled
            }
        except Exception as e:
            return {"error": f"Failed to initialize project: {str(e)}"}
    
    def run_complete_workflow(self, ls_client, create_new_project: bool = True) -> Dict:
        """运行完整的工作流：数据准备 -> 项目创建 -> 存储同步"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized. Call initialize_project() first."}
            
            results = {}
            
            # 1. 数据准备
            if self.project_builder.minio_enabled:
                # 使用MinIO数据源
                data_result = self.project_builder.import_from_minio()
                results["data_import"] = data_result
                
                if data_result.get("error"):
                    return {"error": f"Data import failed: {data_result['error']}"}
            else:
                # 使用传统数据准备流程
                urls = self.project_builder.prepare_data()
                results["data_preparation"] = {"urls": urls}
            
            # 2. 创建Label Studio项目
            if create_new_project:
                project = self.project_builder.create_project(ls_client)
                results["project_creation"] = {"project_id": project.id}
            
            # 3. 创建存储同步
            storage = self.project_builder.create_storage(ls_client)
            results["storage_creation"] = {"storage_id": storage.id}
            
            return {
                "message": "Complete workflow executed successfully",
                "results": results
            }
            
        except Exception as e:
            return {"error": f"Workflow execution failed: {str(e)}"}
    
    def run_data_pipeline(self, pipeline_index: int = 0) -> Dict:
        """运行指定的数据处理管道"""
        try:
            if not self.data_manager:
                return {"error": "Data manager not initialized"}
            
            pipelines = self.config_manager.get_pipeline_configs()
            if not pipelines or pipeline_index >= len(pipelines):
                return {"error": f"Invalid pipeline index: {pipeline_index}"}
            
            pipeline_config = pipelines[pipeline_index]
            result = self.data_manager.create_data_pipeline(pipeline_config)
            
            return result
            
        except Exception as e:
            return {"error": f"Pipeline execution failed: {str(e)}"}
    
    def export_and_store_annotations(self, ls_client, project_id: int, table_name: str = None) -> Dict:
        """导出标注数据并存储到PostgreSQL和MinIO"""
        try:
            # 1. 从Label Studio导出标注
            export_json = export_annotation(
                ls_client, 
                project_id, 
                json_min=True, 
                exclude_skipped=False, 
                only_with_annotation=True
            )
            
            # 2. 转换标注数据
            label_list = simple_json_convertor(
                export_json, 
                True, 
                label_group_name='annotations'
            )
            
            # 3. 存储到PostgreSQL
            table_name = table_name or self.project_builder.project
            label_manager = AnnotationManager()
            
            # 创建标注表（如果不存在）
            label_manager.create_annotation_table(
                table_name, 
                label_name='annotations',
                unique_shot=True, 
                point_allowed=False
            )
            
            # 插入标注数据
            pg_result = label_manager.insert_annotations(
                table_name, 
                label_list, 
                on_conflict='shot'
            )
            
            # 4. 同步标注到MinIO
            minio_result = None
            if self.project_builder.minio_enabled:
                minio_result = self.data_manager.sync_annotations_from_labelstudio(
                    project_id, 
                    prefix="annotations/"
                )
            
            return {
                "message": "Annotations exported and stored successfully",
                "postgresql_result": pg_result,
                "minio_result": minio_result,
                "annotation_count": len(label_list)
            }
            
        except Exception as e:
            return {"error": f"Annotation export failed: {str(e)}"}
    
    def sync_data_bidirectional(self, direction: str = "both") -> Dict:
        """双向数据同步"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized"}
            
            if not self.project_builder.minio_enabled:
                return {"error": "MinIO is not enabled for this project"}
            
            result = self.project_builder.sync_with_minio(direction)
            return result
            
        except Exception as e:
            return {"error": f"Bidirectional sync failed: {str(e)}"}
    
    def cleanup_local_storage(self, ls_client, storage_id: int, keep_storage_link: bool = False) -> Dict:
        """清理本地存储"""
        try:
            from .utils import delete_storage
            
            result = delete_storage(ls_client, storage_id, keep_storage_link)
            return result
            
        except Exception as e:
            return {"error": f"Storage cleanup failed: {str(e)}"}
    
    def get_project_status(self) -> Dict:
        """获取项目状态"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized"}
            
            status = {
                "project_name": self.project_builder.project,
                "minio_enabled": self.project_builder.minio_enabled,
                "data_exported": getattr(self.project_builder, 'data_exported', False),
                "shots_count": len(getattr(self.project_builder, 'shots', [])),
                "minio_config": self.config_manager.get_minio_config(),
                "pipeline_count": len(self.config_manager.get_pipeline_configs())
            }
            
            return {"status": status}
            
        except Exception as e:
            return {"error": f"Failed to get project status: {str(e)}"}
