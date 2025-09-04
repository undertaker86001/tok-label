#!/bin/bash

# MinIO集成环境启动脚本

set -e

echo "=== TOKLABEL MinIO集成环境启动 ==="

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker未运行，请先启动Docker"
    exit 1
fi

echo "✓ Docker检查通过"

# 检查docker-compose是否可用
if ! command -v docker-compose &> /dev/null; then
    echo "错误: docker-compose未安装"
    exit 1
fi

echo "✓ docker-compose检查通过"

# 创建必要的目录
mkdir -p data logs init-scripts

echo "✓ 目录结构创建完成"

# 启动服务
echo "启动MinIO集成服务..."
docker-compose -f docker-compose.minio.yml up -d

echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
docker-compose -f docker-compose.minio.yml ps

# 等待MinIO服务就绪
echo "等待MinIO服务就绪..."
for i in {1..30}; do
    if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        echo "✓ MinIO服务已就绪"
        break
    fi
    echo "等待MinIO服务启动... ($i/30)"
    sleep 2
done

# 检查其他服务
echo "检查其他服务..."
if curl -f http://localhost:6379 > /dev/null 2>&1; then
    echo "✓ Redis服务正常"
else
    echo "⚠ Redis服务可能未就绪"
fi

if curl -f http://localhost:8080 > /dev/null 2>&1; then
    echo "✓ Label Studio服务正常"
else
    echo "⚠ Label Studio服务可能未就绪"
fi

echo ""
echo "=== 服务启动完成 ==="
echo ""
echo "服务访问地址:"
echo "MinIO API: http://localhost:9000"
echo "MinIO Console: http://localhost:9001"
echo "MinIO Web Console: http://localhost:9002"
echo "Label Studio: http://localhost:8080"
echo "Redis: localhost:6379"
echo "PostgreSQL: localhost:5432"
echo ""
echo "默认凭据:"
echo "MinIO: minioadmin/minioadmin"
echo "Label Studio: admin/admin123"
echo "PostgreSQL: toklabel/toklabel123"
echo ""
echo "下一步操作:"
echo "1. 访问MinIO Console创建存储桶"
echo "2. 配置Label Studio项目"
echo "3. 运行测试: python test_package.py"
echo "4. 查看日志: docker-compose -f docker-compose.minio.yml logs"
echo ""
echo "停止服务: docker-compose -f docker-compose.minio.yml down"
