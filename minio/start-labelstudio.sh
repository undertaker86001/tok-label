#!/bin/bash

# Label Studio启动脚本
# 专门为WAV音频标注场景优化

set -e

echo "=== Label Studio启动脚本 ==="

# 设置环境变量
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/data
export LABEL_STUDIO_DISABLE_AUTH=false
export LABEL_STUDIO_USERNAME=admin
export LABEL_STUDIO_PASSWORD=admin123
export LABEL_STUDIO_HOST=0.0.0.0
export LABEL_STUDIO_PORT=8080
export LABEL_STUDIO_DEBUG=false
export LABEL_STUDIO_LOG_LEVEL=INFO

# 创建必要的目录
echo "创建数据目录..."
mkdir -p /data/upload /data/media /data/static /data/logs

# 设置权限
echo "设置目录权限..."
chmod -R 755 /data
chown -R labelstudio:labelstudio /data

# 等待数据库连接
echo "等待PostgreSQL数据库连接..."
until pg_isready -h postgres -p 5432 -U labelstudio; do
    echo "等待PostgreSQL..."
    sleep 2
done

# 等待Redis连接
echo "等待Redis连接..."
until redis-cli -h redis -p 6379 ping; do
    echo "等待Redis..."
    sleep 2
done

# 初始化Label Studio数据库
echo "初始化Label Studio数据库..."
label-studio init --config /app/labelstudio-config.json

# 创建超级用户（如果不存在）
echo "创建超级用户..."
python -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('超级用户创建成功')
else:
    print('超级用户已存在')
"

# 启动Label Studio
echo "启动Label Studio..."
exec label-studio start \
    --host 0.0.0.0 \
    --port 8080 \
    --config /app/labelstudio-config.json \
    --no-browser \
    --no-auth \
    --user admin \
    --password admin123
