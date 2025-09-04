"""
MinIO配置管理器
支持环境变量配置和动态配置管理
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class MinIOConfigManager:
    """MinIO配置管理器，支持环境变量和配置文件"""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，支持环境变量替换"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 替换环境变量
            config_content = self._replace_env_vars(config_content)
            
            # 解析YAML
            config = yaml.safe_load(config_content)
            
            logger.info(f"配置文件加载成功: {self.config_file}")
            return config
            
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return self._get_default_config()
    
    def _replace_env_vars(self, content: str) -> str:
        """替换内容中的环境变量"""
        # 支持 ${VAR:-default} 格式的环境变量
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else ""
            return os.getenv(var_name, default_value)
        
        # 替换 ${VAR:-default} 格式
        content = re.sub(r'\$\{([^:]+)(?::-([^}]*))?\}', replace_var, content)
        
        # 替换 $VAR 格式
        content = re.sub(r'\$([A-Z_][A-Z0-9_]*)', lambda m: os.getenv(m.group(1), ''), content)
        
        return content
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "project": "default_project",
            "description": "默认项目",
            "minio": {
                "enabled": True,
                "bucket": os.getenv("MINIO_BUCKET", "default-bucket"),
                "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                "connection": {
                    "access_key": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                    "secret_key": os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                    "secure": os.getenv("MINIO_SECURE", "false").lower() == "true"
                }
            },
            "label_studio": {
                "url": os.getenv("LABEL_STUDIO_URL", "http://localhost:8080"),
                "api_key": os.getenv("LABEL_STUDIO_API_KEY", "your_api_key_here"),
                "username": os.getenv("LABEL_STUDIO_USERNAME", "admin"),
                "password": os.getenv("LABEL_STUDIO_PASSWORD", "admin123")
            }
        }
    
    def get_minio_config(self) -> Dict[str, Any]:
        """获取MinIO配置"""
        minio_config = self.config.get("minio", {})
        
        # 环境变量覆盖
        return {
            "enabled": minio_config.get("enabled", True),
            "bucket": os.getenv("MINIO_BUCKET", minio_config.get("bucket", "default-bucket")),
            "endpoint": os.getenv("MINIO_ENDPOINT", minio_config.get("endpoint", "localhost:9000")),
            "access_key": os.getenv("MINIO_ACCESS_KEY", minio_config.get("connection", {}).get("access_key", "minioadmin")),
            "secret_key": os.getenv("MINIO_SECRET_KEY", minio_config.get("connection", {}).get("secret_key", "minioadmin")),
            "secure": os.getenv("MINIO_SECURE", str(minio_config.get("connection", {}).get("secure", False))).lower() == "true"
        }
    
    def get_label_studio_config(self) -> Dict[str, Any]:
        """获取Label Studio配置"""
        ls_config = self.config.get("label_studio", {})
        
        return {
            "url": os.getenv("LABEL_STUDIO_URL", ls_config.get("url", "http://localhost:8080")),
            "api_key": os.getenv("LABEL_STUDIO_API_KEY", ls_config.get("api_key", "your_api_key_here")),
            "username": os.getenv("LABEL_STUDIO_USERNAME", ls_config.get("username", "admin")),
            "password": os.getenv("LABEL_STUDIO_PASSWORD", ls_config.get("password", "admin123"))
        }
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        db_config = self.config.get("database", {}).get("postgresql", {})
        
        return {
            "host": os.getenv("POSTGRES_HOST", db_config.get("host", "localhost")),
            "port": int(os.getenv("POSTGRES_PORT", str(db_config.get("port", 5432)))),
            "database": os.getenv("POSTGRES_DB", db_config.get("database", "toklabel")),
            "user": os.getenv("POSTGRES_USER", db_config.get("user", "toklabel")),
            "password": os.getenv("POSTGRES_PASSWORD", db_config.get("password", "toklabel123"))
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0")),
            "password": os.getenv("REDIS_PASSWORD", "")
        }
    
    def get_pipeline_configs(self) -> list:
        """获取管道配置"""
        return self.config.get("pipelines", [])
    
    def get_performance_config(self) -> Dict[str, Any]:
        """获取性能配置"""
        perf_config = self.config.get("performance", {})
        
        return {
            "max_workers": int(os.getenv("MAX_WORKERS", str(perf_config.get("max_workers", 10)))),
            "cache_enabled": os.getenv("CACHE_ENABLED", str(perf_config.get("cache_enabled", True))).lower() == "true",
            "cache_size_mb": int(os.getenv("CACHE_SIZE_MB", str(perf_config.get("cache_size_mb", 1000))))
        }
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        monitor_config = self.config.get("monitoring", {})
        
        return {
            "health_check_interval": monitor_config.get("health_check_interval", 60),
            "storage_statistics": monitor_config.get("storage_statistics", True),
            "data_change_monitoring": monitor_config.get("data_change_monitoring", True),
            "log_level": os.getenv("LOG_LEVEL", monitor_config.get("log_level", "INFO"))
        }
    
    def get_project_info(self) -> Dict[str, Any]:
        """获取项目信息"""
        return {
            "name": self.config.get("project", "default_project"),
            "description": self.config.get("description", "默认项目"),
            "minio_enabled": self.config.get("minio", {}).get("enabled", True)
        }
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 更新配置字典
            for key, value in updates.items():
                keys = key.split('.')
                current = self.config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"配置更新成功: {updates}")
            return True
            
        except Exception as e:
            logger.error(f"配置更新失败: {e}")
            return False
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        errors = []
        warnings = []
        
        # 验证MinIO配置
        minio_config = self.get_minio_config()
        if minio_config["enabled"]:
            if not minio_config["bucket"]:
                errors.append("MinIO bucket未配置")
            if not minio_config["endpoint"]:
                errors.append("MinIO endpoint未配置")
        
        # 验证Label Studio配置
        ls_config = self.get_label_studio_config()
        if not ls_config["url"]:
            errors.append("Label Studio URL未配置")
        if not ls_config["api_key"] or ls_config["api_key"] == "your_api_key_here":
            warnings.append("Label Studio API Key未配置或使用默认值")
        
        # 验证数据库配置
        db_config = self.get_database_config()
        if not db_config["host"]:
            errors.append("数据库主机未配置")
        if not db_config["database"]:
            errors.append("数据库名称未配置")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
