#!/bin/bash

# MinIO集成包安装脚本

set -e

echo "=== TOKLABEL MinIO集成包安装 ==="

# 检查Python版本
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "错误: 需要Python 3.8或更高版本，当前版本: $python_version"
    exit 1
fi

echo "✓ Python版本检查通过: $python_version"

# 创建虚拟环境（可选）
if [ "$1" = "--venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ 虚拟环境已激活"
fi

# 安装依赖
echo "安装依赖包..."
pip install -r requirements.txt

echo "✓ 依赖安装完成"

# 安装MinIO包
echo "安装MinIO集成包..."
pip install -e .

echo "✓ MinIO集成包安装完成"

# 创建配置文件模板
if [ ! -f "project-config-minio.yaml" ]; then
    echo "创建配置文件模板..."
    cat > project-config-minio.yaml << EOF
project: my_project
minio:
  enabled: true
  bucket: tok-label
  prefix: data
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
EOF
    echo "✓ 配置文件模板已创建: project-config-minio.yaml"
fi

# 创建环境变量文件
if [ ! -f ".env" ]; then
    echo "创建环境变量文件..."
    cat > .env << EOF
# MinIO配置
STORAGE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=tok-label
MINIO_SECURE=false

# Label Studio配置
LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_KEY=your_api_key_here

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=toklabel
POSTGRES_USER=toklabel
POSTGRES_PASSWORD=toklabel123
EOF
    echo "✓ 环境变量文件已创建: .env"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步操作:"
echo "1. 启动MinIO服务: docker-compose up -d"
echo "2. 配置Label Studio API密钥: 编辑 .env 文件"
echo "3. 测试连接: python -c \"from minio import MinIOMonitor; m = MinIOMonitor(); print(m.health_check())\""
echo "4. 运行CLI工具: minio-cli --help"
echo ""
echo "文档: README.md"
echo "示例: examples/complete_minio_workflow.py"
echo ""
