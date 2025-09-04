#!/bin/bash

# Label Studio Docker镜像启动脚本
# 专门为WAV音频标注场景优化

set -e

echo "=== Label Studio Docker镜像启动脚本 ==="

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker未运行，请先启动Docker"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: docker-compose未安装"
    exit 1
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p data logs init-scripts

# 构建Label Studio镜像
echo "构建Label Studio镜像..."
docker build -f Dockerfile.labelstudio -t toklabel-labelstudio:latest .

if [ $? -eq 0 ]; then
    echo "✓ Label Studio镜像构建成功"
else
    echo "✗ Label Studio镜像构建失败"
    exit 1
fi

# 启动服务
echo "启动Label Studio及相关服务..."
docker-compose -f docker-compose.minio.yml up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
docker-compose -f docker-compose.minio.yml ps

# 等待Label Studio服务就绪
echo "等待Label Studio服务就绪..."
for i in {1..60}; do
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "✓ Label Studio服务已就绪"
        break
    fi
    echo "等待Label Studio服务启动... ($i/60)"
    sleep 2
done

# 检查其他服务
echo "检查其他服务状态..."
if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "✓ MinIO服务正常"
else
    echo "⚠ MinIO服务可能未就绪"
fi

if curl -f http://localhost:6379 > /dev/null 2>&1; then
    echo "✓ Redis服务正常"
else
    echo "⚠ Redis服务可能未就绪"
fi

if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "✓ PostgreSQL服务正常"
else
    echo "⚠ PostgreSQL服务可能未就绪"
fi

echo ""
echo "=== 服务启动完成 ==="
echo ""
echo "服务访问地址:"
echo "Label Studio: http://localhost:8080"
echo "MinIO API: http://localhost:9000"
echo "MinIO Console: http://localhost:9001"
echo "MinIO Web Console: http://localhost:9002"
echo "Redis: localhost:6379"
echo "PostgreSQL: localhost:5432"
echo ""
echo "默认凭据:"
echo "Label Studio: admin/admin123"
echo "MinIO: minioadmin/minioadmin"
echo "PostgreSQL: toklabel/toklabel123"
echo ""
echo "Label Studio功能:"
echo "- WAV音频文件标注"
echo "- 时间序列标注"
echo "- 文本转写"
echo "- 批量处理"
echo ""
echo "下一步操作:"
echo "1. 访问 http://localhost:8080 登录Label Studio"
echo "2. 创建新的音频标注项目"
echo "3. 上传WAV文件进行标注"
echo "4. 查看日志: docker-compose -f docker-compose.minio.yml logs label-studio"
echo ""
echo "停止服务: docker-compose -f docker-compose.minio.yml down"
echo "重新构建镜像: docker build -f Dockerfile.labelstudio -t toklabel-labelstudio:latest ."
