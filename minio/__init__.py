"""
MinIO集成包
为TOKLABEL项目提供完整的对象存储集成解决方案

主要功能：
- 存储适配器模式，支持本地存储和MinIO存储
- 高级数据管理和处理管道
- 完整的工作流管理
- 监控、验证和性能优化
- 命令行工具和数据迁移工具
"""

__version__ = "1.0.0"
__author__ = "TOKLABEL Team"
__email__ = "team@toklabel.org"

# 核心模块
from .core.minio_data_manager import MinIODataManager
from .core.minio_config_manager import MinIOConfigManager
from .core.minio_workflow_manager import MinIOWorkflowManager
from .core.minio_monitor import MinIOMonitor
from .core.minio_validator import MinIODataValidator
from .core.minio_performance import MinIOPerformanceOptimizer
from .core.minio_importer import MinIOImporter
from .core.storage_adapter import StorageAdapter, LocalStorageAdapter, MinIOStorageAdapter
from .core.wav_audio_manager import WAVAudioManager

# 主要类导出
__all__ = [
    "MinIODataManager",
    "MinIOConfigManager", 
    "MinIOWorkflowManager",
    "MinIOMonitor",
    "MinIODataValidator",
    "MinIOPerformanceOptimizer",
    "MinIOImporter",
    "StorageAdapter",
    "LocalStorageAdapter",
    "MinIOStorageAdapter",
    "WAVAudioManager",
]
