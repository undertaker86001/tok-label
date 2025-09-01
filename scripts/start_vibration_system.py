#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import requests
import json
from typing import Dict, List

def check_service_health(url: str, timeout: int = 30) -> bool:
    """检查服务健康状态"""
    for i in range(timeout):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return False

def start_ml_backend():
    """启动ML后端服务"""
    print("启动振动数据ML后端服务...")
    
    # 设置环境变量
    env = os.environ.copy()
    env.update({
        'LABEL_STUDIO_URL': 'http://localhost:8080',
        'LABEL_STUDIO_API_KEY': 'your_api_key_here',
        'REDIS_HOST': 'localhost',
        'REDIS_PORT': '6379',
        'ML_BACKEND_PORT': '9090'
    })
    
    # 启动服务
    process = subprocess.Popen(
        [sys.executable, 'ml-backends/vibration_phm/_wsgi.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # 等待服务启动
    if check_service_health('http://localhost:9090'):
        print("ML后端服务启动成功")
        return process
    else:
        print("ML后端服务启动失败")
        process.terminate()
        return None

def create_vibration_project():
    """创建振动数据标注项目"""
    print("创建振动数据标注项目...")
    
    try:
        from vibration_project_create import main
        project, storage = main()
        print(f"项目创建成功: {project.title} (ID: {project.id})")
        return project, storage
    except Exception as e:
        print(f"项目创建失败: {e}")
        return None, None

def run_prediction_test(project_id: int):
    """运行预测测试"""
    print("运行预测测试...")
    
    try:
        # 测试预测接口
        test_data = {
            "tasks": [
                {
                    "data": {
                        "shot": 240829001,
                        "csv": "http://file-server:8000/data/vibration_data_240829001.csv"
                    }
                }
            ]
        }
        
        response = requests.post(
            "http://localhost:9090/predict",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            predictions = response.json()
            print(f"预测测试成功: {len(predictions.get('predictions', []))} 个预测结果")
            return True
        else:
            print(f"预测测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"预测测试异常: {e}")
        return False

def main():
    """主函数 - 启动振动数据AI自动化打标系统"""
    print("=== 振动数据AI自动化打标系统启动 ===")
    
    # 1. 检查依赖服务
    print("检查依赖服务...")
    
    # 检查PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='vibration_phm',
            user='postgres',
            password='password'
        )
        conn.close()
        print("PostgreSQL连接正常")
    except Exception as e:
        print(f"PostgreSQL连接失败: {e}")
        return
    
    # 检查Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("Redis连接正常")
    except Exception as e:
        print(f"Redis连接失败: {e}")
        return
    
    # 检查Label Studio
    if not check_service_health('http://localhost:8080'):
        print("Label Studio服务未启动，请先启动Label Studio")
        return
    
    # 2. 启动ML后端
    ml_process = start_ml_backend()
    if not ml_process:
        print("ML后端启动失败，系统启动终止")
        return
    
    # 3. 创建项目
    project, storage = create_vibration_project()
    if not project:
        print("项目创建失败，系统启动终止")
        ml_process.terminate()
        return
    
    # 4. 运行预测测试
    if run_prediction_test(project.id):
        print("预测功能测试通过")
    else:
        print("预测功能测试失败")
    
    print("=== 系统启动完成 ===")
    print(f"项目ID: {project.id}")
    print(f"存储ID: {storage.id}")
    print("ML后端服务运行在: http://localhost:9090")
    print("Label Studio访问地址: http://localhost:8080")
    
    try:
        # 保持服务运行
        ml_process.wait()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭服务...")
        ml_process.terminate()
        print("系统已关闭")

if __name__ == "__main__":
    main()
