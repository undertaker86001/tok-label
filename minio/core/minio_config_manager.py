import yaml
import os
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class MinIOConfigManager:
    """MinIO配置管理器，处理项目配置和MinIO集成设置"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config = {}
        if config_file and os.path.exists(config_file):
            self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config file {self.config_file}: {e}")
            self.config = {}
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Error saving config file {self.config_file}: {e}")
    
    def enable_minio(self, 
                     bucket: str = None, 
                     prefix: str = "", 
                     auto_sync: bool = False,
                     import_pattern: str = r'/(\d+)\.csv$',
                     minio_config: Dict = None) -> Dict:
        """
        启用MinIO集成
        
        参数:
        bucket: 存储桶名称
        prefix: 对象前缀
        auto_sync: 是否自动同步
        import_pattern: 导入文件名模式
        minio_config: MinIO连接配置
        
        返回:
        Dict: 操作结果
        """
        try:
            # 使用传入的配置或默认配置
            if minio_config:
                endpoint = minio_config.get('endpoint', 'localhost:9000')
                access_key = minio_config.get('access_key', 'minioadmin')
                secret_key = minio_config.get('secret_key', 'minioadmin')
            else:
                endpoint = 'localhost:9000'
                access_key = 'minioadmin'
                secret_key = 'minioadmin'
            
            minio_config_dict = {
                "enabled": True,
                "bucket": bucket or 'tok-label',
                "prefix": prefix,
                "auto_sync": auto_sync,
                "import_pattern": import_pattern,
                "endpoint": endpoint,
                "connection": {
                    "access_key": access_key,
                    "secret_key": secret_key
                }
            }
            
            self.config["minio"] = minio_config_dict
            
            if self.config_file:
                self.save_config()
            
            return {
                "message": "MinIO integration enabled successfully",
                "config": minio_config_dict
            }
            
        except Exception as e:
            return {"error": f"Failed to enable MinIO: {str(e)}"}
    
    def disable_minio(self) -> Dict:
        """禁用MinIO集成"""
        try:
            if "minio" in self.config:
                self.config["minio"]["enabled"] = False
                
                if self.config_file:
                    self.save_config()
                
                return {"message": "MinIO integration disabled successfully"}
            else:
                return {"message": "MinIO was not enabled"}
                
        except Exception as e:
            return {"error": f"Failed to disable MinIO: {str(e)}"}
    
    def get_minio_config(self) -> Dict:
        """获取MinIO配置"""
        return self.config.get("minio", {})
    
    def is_minio_enabled(self) -> bool:
        """检查MinIO是否启用"""
        minio_config = self.get_minio_config()
        return minio_config.get("enabled", False)
    
    def create_data_pipeline_config(self, 
                                   source_type: str,
                                   source_config: Dict,
                                   processors: List[Dict] = None,
                                   destination_prefix: str = "") -> Dict:
        """
        创建数据管道配置
        
        参数:
        source_type: 数据源类型 ("postgres", "minio")
        source_config: 数据源配置
        processors: 处理器列表
        destination_prefix: 目标前缀
        
        返回:
        Dict: 管道配置
        """
        pipeline_config = {
            "source": {
                "type": source_type,
                "config": source_config
            },
            "processors": processors or [],
            "destination": {
                "type": "minio",
                "prefix": destination_prefix
            },
            "max_workers": 10
        }
        
        # 保存到配置文件
        if "pipelines" not in self.config:
            self.config["pipelines"] = []
        
        self.config["pipelines"].append(pipeline_config)
        
        if self.config_file:
            self.save_config()
        
        return pipeline_config
    
    def get_pipeline_configs(self) -> List[Dict]:
        """获取所有管道配置"""
        return self.config.get("pipelines", [])
    
    def remove_pipeline_config(self, index: int) -> Dict:
        """删除指定索引的管道配置"""
        try:
            pipelines = self.config.get("pipelines", [])
            if 0 <= index < len(pipelines):
                removed_pipeline = pipelines.pop(index)
                if self.config_file:
                    self.save_config()
                return {
                    "message": f"Pipeline config at index {index} removed successfully",
                    "removed_config": removed_pipeline
                }
            else:
                return {"error": f"Invalid pipeline index: {index}"}
        except Exception as e:
            return {"error": f"Failed to remove pipeline config: {str(e)}"}
    
    def update_minio_settings(self, **kwargs) -> Dict:
        """更新MinIO设置"""
        try:
            if "minio" not in self.config:
                self.config["minio"] = {}
            
            # 更新设置
            for key, value in kwargs.items():
                if key in ["bucket", "prefix", "auto_sync", "import_pattern", "enabled"]:
                    self.config["minio"][key] = value
            
            if self.config_file:
                self.save_config()
            
            return {
                "message": "MinIO settings updated successfully",
                "updated_config": self.config["minio"]
            }
        except Exception as e:
            return {"error": f"Failed to update MinIO settings: {str(e)}"}
