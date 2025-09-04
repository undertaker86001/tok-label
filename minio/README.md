# TOKLABEL MinIO集成包

独立的MinIO功能模块，为TOKLABEL项目提供完整的对象存储集成解决方案。

## 功能特性

### 🚀 核心功能
- **存储适配器模式**: 支持本地存储和MinIO存储的无缝切换
- **高级数据管理**: 批量数据处理、同步和转换
- **数据处理管道**: 支持PostgreSQL到MinIO的数据流
- **完整工作流**: 从数据准备到标注的完整流程管理

### 🔧 工具和监控
- **命令行工具**: 完整的CLI界面
- **数据验证**: CSV格式验证、数据一致性检查
- **性能优化**: 并发上传/下载、数据缓存
- **监控系统**: 健康检查、统计信息、数据变化监控

### 📦 部署支持
- **Docker支持**: 完整的容器化部署
- **Kubernetes支持**: 生产级K8s部署配置
- **数据迁移**: 从本地存储和Redis迁移到MinIO

## 快速开始

### 安装

```bash
# 从本地安装
cd minio
pip install -e .

# 或直接安装依赖
pip install minio>=7.1.0 click>=8.0.0 pyyaml>=6.0 pandas>=1.3.0
```

### 基本使用

```python
from minio import MinIODataManager, MinIOConfigManager

# 创建配置管理器
config_manager = MinIOConfigManager('project-config.yaml')

# 启用MinIO集成
config_manager.enable_minio(
    bucket='my-bucket',
    prefix='data/',
    minio_config={
        'endpoint': 'localhost:9000',
        'access_key': 'minioadmin',
        'secret_key': 'minioadmin'
    }
)

# 创建数据管理器
data_manager = MinIODataManager('my-project', bucket='my-bucket')

# 批量处理数据
result = data_manager.batch_process_and_upload(
    data_processor=lambda shot: pd.DataFrame({'time': [1, 2, 3], 'value': [shot, shot*2, shot*3]}),
    shots=[1, 2, 3],
    prefix='processed/'
)
```

### 命令行工具

```bash
# 启用MinIO集成
minio-cli enable --config project-config.yaml --bucket my-bucket

# 导入数据
minio-cli import-data --config project-config.yaml --prefix data/

# 健康检查
minio-cli health-check --bucket my-bucket

# 数据验证
minio-cli validate --config project-config.yaml --required-columns time,value
```

## 架构设计

### 存储适配器模式
```
StorageAdapter (抽象基类)
├── LocalStorageAdapter (本地存储)
└── MinIOStorageAdapter (MinIO存储)
```

### 数据处理管道
```
PostgreSQL → 数据处理器链 → MinIO → Label Studio
```

### 配置层次
```
环境变量 → 配置文件 → 项目配置 → 运行时配置
```

## 高级功能

### 数据处理管道

```python
from minio import MinIODataManager

# 创建数据管理器
data_manager = MinIODataManager('plasma_analysis')

# 定义管道配置
pipeline_config = {
    "source": {
        "type": "postgres",
        "config": {
            "shots": [240830030, 240830031],
            "name_table_columns": {
                "ammeter": ["ammeter", ["CS1", "CS2"]]
            }
        }
    },
    "processors": [
        {
            "type": "filter",
            "config": {"condition": "time >= 0.1 and time <= 1.5"}
        },
        {
            "type": "normalize",
            "config": {"columns": ["CS1", "CS2"], "method": "zscore"}
        }
    ],
    "destination": {
        "type": "minio",
        "prefix": "processed"
    }
}

# 执行管道
result = data_manager.create_data_pipeline(pipeline_config)
```

### 性能优化

```python
from minio import MinIOPerformanceOptimizer

# 创建性能优化器
optimizer = MinIOPerformanceOptimizer(bucket='my-bucket', max_workers=20)

# 并行上传多个DataFrame
data_dict = {
    'shot1.csv': df1,
    'shot2.csv': df2,
    'shot3.csv': df3
}

result = optimizer.parallel_upload_dataframes(data_dict, prefix='data/')

# 并行下载
file_paths = ['data/shot1.csv', 'data/shot2.csv', 'data/shot3.csv']
download_result = optimizer.parallel_download_dataframes(file_paths, use_cache=True)
```

## 配置示例

### 项目配置文件 (project-config-minio.yaml)

```yaml
project: plasma_analysis
minio:
  enabled: true
  bucket: tok-label
  prefix: plasma_data
  auto_sync: true
  import_pattern: '/(\d+)\.csv$'
  endpoint: localhost:9000
  connection:
    access_key: minioadmin
    secret_key: minioadmin

pipelines:
  - source:
      type: postgres
      config:
        shots: [240830030, 240830031]
        name_table_columns:
          ammeter: ["ammeter", ["CS1", "CS2"]]
    processors:
      - type: filter
        config:
          condition: "time > 0"
      - type: normalize
        config:
          columns: ["CS1", "CS2"]
          method: "zscore"
    destination:
      type: minio
      prefix: processed
```

## 部署

### Docker部署

```bash
# 使用提供的Docker Compose配置
docker-compose -f minio/k8s/docker-compose.minio.yml up -d
```

### Kubernetes部署

```bash
# 部署MinIO服务
kubectl apply -f minio/k8s/minio-deployment.yaml
```

## 测试

```bash
# 运行集成测试
cd minio
python -m pytest tests/ -v

# 运行特定测试
python tests/integration_test_minio.py
```