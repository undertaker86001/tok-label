#!/usr/bin/env python3
"""
MinIO集成设置脚本
"""

import os
import sys
import yaml
import argparse
from pathlib import Path

def setup_minio_environment(config_file: str, minio_endpoint: str, bucket_name: str):
    """设置MinIO环境配置"""
    
    # 1. 更新环境变量文件
    env_file = Path('.env')
    env_content = []
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.readlines()
    
    # 添加或更新MinIO配置
    minio_vars = {
        'STORAGE_BACKEND': 'minio',
        'MINIO_ENDPOINT': minio_endpoint,
        'MINIO_BUCKET': bucket_name,
        'MINIO_ACCESS_KEY': 'minioadmin',
        'MINIO_SECRET_KEY': 'minioadmin',
        'MINIO_SECURE': 'false'
    }
    
    # 更新或添加环境变量
    for var, value in minio_vars.items():
        found = False
        for i, line in enumerate(env_content):
            if line.startswith(f"{var}="):
                env_content[i] = f"{var}={value}\n"
                found = True
                break
        if not found:
            env_content.append(f"{var}={value}\n")
    
    with open(env_file, 'w') as f:
        f.writelines(env_content)
    
    print(f"✓ 已更新 {env_file} 文件")
    
    # 2. 更新项目配置文件
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # 添加MinIO配置
    config['minio'] = {
        'enabled': True,
        'bucket': bucket_name,
        'prefix': f"{config.get('project', 'default')}_data",
        'auto_sync': True,
        'import_pattern': r'/(\d+)\.csv$'
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"✓ 已更新 {config_file} 配置文件")
    
    # 3. 创建测试脚本
    test_script = Path('test_minio_connection.py')
    test_content = f"""#!/usr/bin/env python3
import os
from minio import Minio
from minio.error import S3Error

def test_minio_connection():
    try:
        client = Minio(
            '{minio_endpoint}',
            access_key='minioadmin',
            secret_key='minioadmin',
            secure=False
        )
        
        # 测试连接
        buckets = client.list_buckets()
        print(f"✓ MinIO连接成功，发现 {{len(buckets)}} 个存储桶")
        
        # 检查目标桶
        if client.bucket_exists('{bucket_name}'):
            print(f"✓ 存储桶 '{bucket_name}' 已存在")
        else:
            client.make_bucket('{bucket_name}')
            print(f"✓ 已创建存储桶 '{bucket_name}'")
        
        return True
        
    except S3Error as e:
        print(f"✗ MinIO S3错误: {{e}}")
        return False
    except Exception as e:
        print(f"✗ MinIO连接错误: {{e}}")
        return False

if __name__ == "__main__":
    success = test_minio_connection()
    sys.exit(0 if success else 1)
"""
    
    with open(test_script, 'w') as f:
        f.write(test_content)
    
    os.chmod(test_script, 0o755)
    print(f"✓ 已创建测试脚本 {test_script}")

def create_docker_compose_override():
    """创建Docker Compose覆盖文件"""
    
    override_content = """version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: tok-label-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - tok-label-network

  file-server:
    environment:
      - STORAGE_BACKEND=minio
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET=tok-label
      - MINIO_SECURE=false
    depends_on:
      - minio
    networks:
      - tok-label-network

volumes:
  minio_data:

networks:
  tok-label-network:
    driver: bridge
"""
    
    with open('docker-compose.minio.yml', 'w') as f:
        f.write(override_content)
    
    print("✓ 已创建 docker-compose.minio.yml 文件")

def main():
    parser = argparse.ArgumentParser(description='设置MinIO集成')
    parser.add_argument('--config', default='project-config.yaml', help='项目配置文件路径')
    parser.add_argument('--endpoint', default='localhost:9000', help='MinIO端点')
    parser.add_argument('--bucket', default='tok-label', help='MinIO存储桶名称')
    parser.add_argument('--docker', action='store_true', help='创建Docker Compose配置')
    
    args = parser.parse_args()
    
    print("=== MinIO集成设置 ===")
    
    # 设置环境
    setup_minio_environment(args.config, args.endpoint, args.bucket)
    
    # 创建Docker配置（如果需要）
    if args.docker:
        create_docker_compose_override()
    
    print("\n=== 设置完成 ===")
    print("请运行以下命令测试MinIO连接:")
    print("python test_minio_connection.py")
    
    if args.docker:
        print("\n启动MinIO服务:")
        print("docker-compose -f docker-compose.minio.yml up -d")

if __name__ == "__main__":
    main()
