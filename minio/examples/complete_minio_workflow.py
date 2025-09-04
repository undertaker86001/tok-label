#!/usr/bin/env python3
"""
完整的MinIO集成工作流示例
"""

import toklabel
from toklabel.minio_workflow_manager import MinIOWorkflowManager
import json

def main():
    """主工作流示例"""
    
    # 1. 连接Label Studio
    API_KEY = 'your_api_key_here'
    ls = toklabel.connect_Label_Studio(API_key=API_KEY)
    
    # 2. 初始化工作流管理器
    workflow = MinIOWorkflowManager('project-config-minio.yaml')
    
    # 3. 初始化项目
    init_result = workflow.initialize_project()
    print("项目初始化结果:", json.dumps(init_result, indent=2, ensure_ascii=False))
    
    if init_result.get("error"):
        return
    
    # 4. 运行完整工作流
    workflow_result = workflow.run_complete_workflow(ls, create_new_project=True)
    print("工作流执行结果:", json.dumps(workflow_result, indent=2, ensure_ascii=False))
    
    if workflow_result.get("error"):
        return
    
    project_id = workflow_result["results"]["project_creation"]["project_id"]
    storage_id = workflow_result["results"]["storage_creation"]["storage_id"]
    
    # 5. 运行数据处理管道
    pipeline_result = workflow.run_data_pipeline(pipeline_index=0)
    print("数据管道执行结果:", json.dumps(pipeline_result, indent=2, ensure_ascii=False))
    
    # 6. 获取项目状态
    status = workflow.get_project_status()
    print("项目状态:", json.dumps(status, indent=2, ensure_ascii=False))
    
    # 7. 模拟标注完成后的导出流程
    print("\n=== 标注完成后的操作 ===")
    
    # 导出并存储标注
    annotation_result = workflow.export_and_store_annotations(
        ls, project_id, table_name="plasma_annotations"
    )
    print("标注导出结果:", json.dumps(annotation_result, indent=2, ensure_ascii=False))
    
    # 8. 双向同步
    sync_result = workflow.sync_data_bidirectional(direction="both")
    print("双向同步结果:", json.dumps(sync_result, indent=2, ensure_ascii=False))
    
    # 9. 清理本地存储（可选）
    cleanup_result = workflow.cleanup_local_storage(ls, storage_id, keep_storage_link=True)
    print("存储清理结果:", json.dumps(cleanup_result, indent=2, ensure_ascii=False))

def advanced_pipeline_example():
    """高级管道使用示例"""
    
    # 1. 创建配置管理器
    from toklabel.minio_config_manager import MinIOConfigManager
    config_manager = MinIOConfigManager('project-config-minio.yaml')
    
    # 2. 动态创建新的数据管道
    pipeline_config = config_manager.create_data_pipeline_config(
        source_type="postgres",
        source_config={
            "shots": [240830030, 240830031],
            "name_table_columns": {
                "ammeter": ["ammeter", ["CS1", "CS2"]],
                "flux_loop": ["flux_loop", [1, 2, 3]]
            },
            "t_min": 0.0,
            "t_max": 2.0,
            "resolution": 1e-3
        },
        processors=[
            {
                "type": "filter",
                "config": {"condition": "time >= 0.1 and time <= 1.5"}
            },
            {
                "type": "normalize",
                "config": {"columns": ["CS1", "CS2"], "method": "zscore"}
            }
        ],
        destination_prefix="advanced_processed"
    )
    
    print("创建的管道配置:", json.dumps(pipeline_config, indent=2, ensure_ascii=False))
    
    # 3. 执行管道
    from toklabel.minio_data_manager import MinIODataManager
    data_manager = MinIODataManager("plasma_analysis_advanced")
    pipeline_result = data_manager.create_data_pipeline(pipeline_config)
    print("管道执行结果:", json.dumps(pipeline_result, indent=2, ensure_ascii=False))

def batch_annotation_sync_example():
    """批量标注同步示例"""
    
    from toklabel.minio_data_manager import MinIODataManager
    
    # 创建数据管理器
    data_manager = MinIODataManager("plasma_analysis")
    
    # 假设有一个Label Studio项目ID
    project_id = 123
    
    # 同步标注数据到MinIO
    sync_result = data_manager.sync_annotations_from_labelstudio(
        project_id, 
        prefix="annotations/plasma_2024/"
    )
    print("标注同步结果:", json.dumps(sync_result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    print("=== 完整工作流示例 ===")
    main()
    
    print("\n=== 高级管道示例 ===")
    advanced_pipeline_example()
    
    print("\n=== 批量标注同步示例 ===")
    batch_annotation_sync_example()
