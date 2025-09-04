#!/usr/bin/env python3
"""
配置检查脚本
验证MinIO和Label Studio的配置是否正确
"""

import os
import sys
import requests
import psycopg2
import redis
from minio import Minio
from urllib.parse import urlparse

def check_env_vars():
    """检查环境变量配置"""
    print("=== 环境变量检查 ===")
    
    env_vars = {
        "MinIO": {
            "MINIO_ENDPOINT": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            "MINIO_ACCESS_KEY": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            "MINIO_SECRET_KEY": os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            "MINIO_BUCKET": os.getenv("MINIO_BUCKET", "tok-label"),
            "MINIO_SECURE": os.getenv("MINIO_SECURE", "false")
        },
        "Label Studio": {
            "LABEL_STUDIO_URL": os.getenv("LABEL_STUDIO_URL", "http://localhost:8080"),
            "LABEL_STUDIO_USERNAME": os.getenv("LABEL_STUDIO_USERNAME", "admin"),
            "LABEL_STUDIO_PASSWORD": os.getenv("LABEL_STUDIO_PASSWORD", "admin123"),
            "LABEL_STUDIO_PORT": os.getenv("LABEL_STUDIO_PORT", "8080")
        },
        "PostgreSQL": {
            "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
            "POSTGRES_DB": os.getenv("POSTGRES_DB", "label_studio"),
            "POSTGRES_USER": os.getenv("POSTGRES_USER", "labelstudio"),
            "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "labelstudio123")
        },
        "Redis": {
            "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
            "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
            "REDIS_DB": os.getenv("REDIS_DB", "0"),
            "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", "")
        }
    }
    
    for service, vars in env_vars.items():
        print(f"\n{service}配置:")
        for key, value in vars.items():
            print(f"  {key}: {value}")
    
    return env_vars

def check_minio_connection(minio_config):
    """检查MinIO连接"""
    print("\n=== MinIO连接检查 ===")
    
    try:
        endpoint = minio_config["MINIO_ENDPOINT"]
        access_key = minio_config["MINIO_ACCESS_KEY"]
        secret_key = minio_config["MINIO_SECRET_KEY"]
        secure = minio_config["MINIO_SECURE"].lower() == "true"
        
        # 解析endpoint
        if "://" not in endpoint:
            endpoint = f"http{'s' if secure else ''}://{endpoint}"
        
        parsed_url = urlparse(endpoint)
        host = parsed_url.hostname
        port = parsed_url.port or (443 if secure else 9000)
        
        print(f"连接MinIO: {host}:{port}")
        
        client = Minio(
            f"{host}:{port}",
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # 检查连接
        buckets = client.list_buckets()
        print(f"✓ MinIO连接成功，找到 {len(list(buckets))} 个存储桶")
        
        # 检查指定存储桶
        bucket_name = minio_config["MINIO_BUCKET"]
        if client.bucket_exists(bucket_name):
            print(f"✓ 存储桶 '{bucket_name}' 存在")
        else:
            print(f"⚠ 存储桶 '{bucket_name}' 不存在")
            try:
                client.make_bucket(bucket_name)
                print(f"✓ 已创建存储桶 '{bucket_name}'")
            except Exception as e:
                print(f"✗ 创建存储桶失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ MinIO连接失败: {e}")
        return False

def check_label_studio_connection(ls_config):
    """检查Label Studio连接"""
    print("\n=== Label Studio连接检查 ===")
    
    try:
        url = ls_config["LABEL_STUDIO_URL"]
        username = ls_config["LABEL_STUDIO_USERNAME"]
        password = ls_config["LABEL_STUDIO_PASSWORD"]
        
        print(f"连接Label Studio: {url}")
        
        # 检查健康状态
        health_url = f"{url}/health"
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            print("✓ Label Studio服务正常")
            
            # 尝试登录
            login_url = f"{url}/api/auth/login/"
            login_data = {
                "username": username,
                "password": password
            }
            
            login_response = requests.post(login_url, json=login_data, timeout=10)
            
            if login_response.status_code == 200:
                print("✓ Label Studio登录成功")
                return True
            else:
                print(f"⚠ Label Studio登录失败: {login_response.status_code}")
                return False
        else:
            print(f"✗ Label Studio服务异常: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Label Studio连接失败: {e}")
        return False

def check_postgres_connection(pg_config):
    """检查PostgreSQL连接"""
    print("\n=== PostgreSQL连接检查 ===")
    
    try:
        host = pg_config["POSTGRES_HOST"]
        port = int(pg_config["POSTGRES_PORT"])
        database = pg_config["POSTGRES_DB"]
        user = pg_config["POSTGRES_USER"]
        password = pg_config["POSTGRES_PASSWORD"]
        
        print(f"连接PostgreSQL: {host}:{port}/{database}")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        print(f"✓ PostgreSQL连接成功，版本: {version[0]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"✗ PostgreSQL连接失败: {e}")
        return False

def check_redis_connection(redis_config):
    """检查Redis连接"""
    print("\n=== Redis连接检查 ===")
    
    try:
        host = redis_config["REDIS_HOST"]
        port = int(redis_config["REDIS_PORT"])
        db = int(redis_config["REDIS_DB"])
        password = redis_config["REDIS_PASSWORD"]
        
        print(f"连接Redis: {host}:{port}")
        
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            decode_responses=True
        )
        
        # 测试连接
        r.ping()
        print("✓ Redis连接成功")
        
        # 获取信息
        info = r.info()
        print(f"  Redis版本: {info.get('redis_version', 'unknown')}")
        print(f"  已用内存: {info.get('used_memory_human', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"✗ Redis连接失败: {e}")
        return False

def main():
    """主函数"""
    print("MinIO和Label Studio配置检查工具")
    print("=" * 50)
    
    # 检查环境变量
    env_vars = check_env_vars()
    
    # 检查各服务连接
    results = {
        "MinIO": check_minio_connection(env_vars["MinIO"]),
        "Label Studio": check_label_studio_connection(env_vars["Label Studio"]),
        "PostgreSQL": check_postgres_connection(env_vars["PostgreSQL"]),
        "Redis": check_redis_connection(env_vars["Redis"])
    }
    
    # 总结
    print("\n=== 检查结果总结 ===")
    all_passed = True
    for service, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{service}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有服务配置正确，可以正常使用！")
        return 0
    else:
        print("\n⚠ 部分服务配置有问题，请检查相关配置。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
