#!/bin/bash

# 音频标注ML Backend启动脚本

echo "启动音频标注ML Backend服务..."

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker未运行，请先启动Docker服务"
    exit 1
fi

# 构建Docker镜像
echo "构建ML Backend镜像..."
docker build -t audio-annotation-ml-backend:latest .

if [ $? -ne 0 ]; then
    echo "错误: Docker镜像构建失败"
    exit 1
fi

# 创建必要的目录
echo "创建数据目录..."
mkdir -p data/server
mkdir -p models

# 启动服务
echo "启动ML Backend服务..."
docker-compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
if curl -s http://localhost:9090/ > /dev/null; then
    echo "✅ 音频标注ML Backend启动成功！"
    echo "服务地址: http://localhost:9090"
    echo "在Label Studio中添加模型时使用此URL"
else
    echo "❌ 服务启动失败，请检查日志:"
    docker-compose logs
    exit 1
fi

echo ""
echo "使用说明:"
echo "1. 在Label Studio项目设置中添加ML Backend模型"
echo "2. URL设置为: http://localhost:9090"
echo "3. 查看日志: docker-compose logs -f"
echo "4. 停止服务: docker-compose down"
