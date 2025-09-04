#!/usr/bin/env python3
"""
MinIO集成完整测试脚本
"""

import unittest
import tempfile
import os
import json
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestCompleteMinIOIntegration(unittest.TestCase):
    """完整的MinIO集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_content = """
project: integration_test
file_path: test_data
shots: [1, 2, 3]
minio:
  enabled: true
  bucket: test-bucket
  prefix: test_prefix
  auto_sync: true
pipelines:
  - source:
      type: postgres
      config:
        shots: [1, 2, 3]
        name_table_columns:
          test_table: ["test_table", ["col1", "col2"]]
    processors:
      - type: filter
        config:
          condition: "time > 0"
    destination:
      type: minio
      prefix: processed
"""
        self.test_config.write(config_content)
        self.test_config.close()
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.test_config.name)
    
    @patch('toklabel.utils.upload_to_minio')
    @patch('toklabel.utils.download_from_minio')
    @patch('toklabel.utils.list_minio_objects')
    def test_complete_workflow(self, mock_list, mock_download, mock_upload):
        """测试完整工作流"""
        # 模拟MinIO操作
        mock_list.return_value = ["test_prefix/integration_test/1.csv", "test_prefix/integration_test/2.csv"]
        mock_download.return_value = "time,col1,col2\n1.0,10,20\n2.0,15,25\n".encode('utf-8')
        mock_upload.return_value = {"message": "Success", "path": "test/path.csv"}
        
        from toklabel.minio_workflow_manager import MinIOWorkflowManager
        
        # 初始化工作流
        workflow = MinIOWorkflowManager(self.test_config.name)
        
        with patch.object(workflow, 'project_builder') as mock_pb:
            mock_pb.project = "integration_test"
            mock_pb.minio_enabled = True
            mock_pb.minio_bucket = "test-bucket"
            
            # 测试初始化
            result = workflow.initialize_project()
            self.assertNotIn("error", result)
            
            # 测试数据管道
            with patch.object(workflow, 'data_manager') as mock_dm:
                mock_dm.create_data_pipeline.return_value = {
                    "message": "Pipeline completed successfully",
                    "uploaded_files": [{"shot": 1}, {"shot": 2}]
                }
                
                pipeline_result = workflow.run_data_pipeline(0)
                self.assertNotIn("error", pipeline_result)
    
    def test_performance_optimization(self):
        """测试性能优化功能"""
        from toklabel.minio_performance import MinIOPerformanceOptimizer
        
        optimizer = MinIOPerformanceOptimizer(bucket="test-bucket", max_workers=5)
        
        # 测试缓存统计
        cache_stats = optimizer.get_cache_stats()
        self.assertEqual(cache_stats["cached_files"], 0)
        
        # 测试缓存清理
        optimizer.clear_cache()
        self.assertEqual(len(optimizer.cache), 0)

class TestMinIOWorkflow(unittest.TestCase):
    """MinIO工作流测试"""
    
    def setUp(self):
        """测试设置"""
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_content = """
project: workflow_test
minio:
  enabled: true
  bucket: workflow-bucket
  prefix: workflow_data
  auto_sync: true
pipelines:
  - source:
      type: postgres
      config:
        shots: [1, 2, 3]
    processors:
      - type: filter
        config:
          condition: "time > 0"
    destination:
      type: minio
      prefix: processed
"""
        self.temp_config.write(config_content)
        self.temp_config.close()
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.temp_config.name)
    
    @patch('toklabel.minio_workflow_manager.ProjectBuilder')
    @patch('toklabel.minio_workflow_manager.MinIODataManager')
    def test_workflow_manager_initialization(self, mock_data_manager, mock_project_builder):
        """测试工作流管理器初始化"""
        from toklabel.minio_workflow_manager import MinIOWorkflowManager
        
        # 模拟ProjectBuilder
        mock_pb_instance = MagicMock()
        mock_pb_instance.project = "workflow_test"
        mock_pb_instance.minio_enabled = True
        mock_pb_instance.minio_bucket = "workflow-bucket"
        mock_project_builder.return_value = mock_pb_instance
        
        # 创建工作流管理器
        workflow = MinIOWorkflowManager(self.temp_config.name)
        result = workflow.initialize_project()
        
        self.assertNotIn("error", result)
        self.assertEqual(result["project_name"], "workflow_test")
        self.assertTrue(result["minio_enabled"])

if __name__ == '__main__':
    # 运行所有测试
    unittest.main(verbosity=2)
