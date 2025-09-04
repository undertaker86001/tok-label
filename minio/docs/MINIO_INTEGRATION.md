# MinIO集成指南

本文档介绍如何在TOKLABEL项目中集成和使用MinIO对象存储。

## 概述

MinIO集成提供了以下功能：
- 替代本地文件存储，使用MinIO作为后端存储
- 支持从MinIO批量导入数据到Label Studio
- 提供数据处理管道，支持PostgreSQL到MinIO的数据流
- 双向数据同步功能
- 完整的数据验证和监控工具

## 快速开始

### 1. 安装依赖

```bash
pip install minio>=7.1.0 click>=8.0.0
```

### 2. 配置MinIO

```bash
# 使用设置脚本
python scripts/setup_minio_integration.py --config project-config.yaml --endpoint localhost:9000 --bucket tok-label --docker

# 或手动配置环境变量
export STORAGE_BACKEND=minio
export MINIO_ENDPOINT=localhost:9000
export MINIO_BUCKET=tok-label
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
```

### 3. 启动MinIO服务

```bash
# 使用Docker Compose
docker-compose -f docker-compose.minio.yml up -d

# 或使用Kubernetes
kubectl apply -f k8s/minio-deployment.yaml
```

### 4. 测试连接

```bash
python test_minio_connection.py
```

## 使用方法

### 命令行工具

```bash
# 启用MinIO集成
python cli/minio_cli.py enable --config project-config.yaml --bucket tok-label --auto-sync

# 从MinIO导入数据
python cli/minio_cli.py import-data --config project-config.yaml --prefix plasma_data

# 导出数据到MinIO
python cli/minio_cli.py export-data --config project-config.yaml --include-annotations

# 运行数据处理管道
python cli/minio_cli.py run-pipeline --config project-config.yaml --pipeline-index 0

# 健康检查
python cli/minio_cli.py health-check --bucket tok-label

# 数据验证
python cli/minio_cli.py validate --config project-config.yaml --required-columns time,CS1,CS2

# 数据迁移
python cli/minio_cli.py migrate --local-dir ./data --project plasma_analysis --mode both
```

### Python API

```python
import toklabel
from toklabel.minio_workflow_manager import MinIOWorkflowManager

# 1. 初始化工作流
workflow = MinIOWorkflowManager('project-config-minio.yaml')
workflow.initialize_project()

# 2. 连接Label Studio
ls = toklabel.connect_Label_Studio(API_key='your_api_key')

# 3. 运行完整工作流
result = workflow.run_complete_workflow(ls)

# 4. 运行数据管道
pipeline_result = workflow.run_data_pipeline(0)

# 5. 导出标注数据
annotation_result = workflow.export_and_store_annotations(ls, project_id, "annotations_table")
```

### 配置文件示例

参考 `project-config-minio.yaml` 获取完整的配置示例。

## 故障排除

### 常见问题

1. 连接失败: 检查MinIO端点和凭证配置
2. 上传失败: 检查存储桶权限和网络连接
3. 数据验证失败: 使用验证工具检查数据格式

### 日志查看

```bash
# 查看文件服务器日志
docker logs tok-label-file-server

# 查看MinIO日志
docker logs tok-label-minio
```

## 性能优化

- 使用并发上传/下载提高性能
- 启用数据缓存减少重复下载
- 合理配置max_workers参数

## 安全注意事项

- 在生产环境中使用强密码
- 启用HTTPS连接
- 配置适当的存储桶策略
