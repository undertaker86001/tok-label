#!/usr/bin/env python3
"""
WAV音频标注工作流示例
演示如何使用MinIO adapter进行WAV文件的音频标注
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from minio.core.minio_workflow_manager import MinIOWorkflowManager
from label_studio_sdk import Client
import psycopg2

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """主函数：演示WAV音频标注工作流"""
    
    # 配置参数
    config_file = "minio/project-config-wav-audio.yaml"
    wav_files_dir = "data/wav_files"  # WAV文件目录
    label_studio_url = "http://localhost:8080"
    label_studio_api_key = "your_api_key_here"
    
    # 数据库连接参数
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "audio_annotations",
        "user": "audio_user",
        "password": "audio_password"
    }
    
    try:
        # 1. 初始化工作流管理器
        logger.info("初始化WAV音频工作流管理器...")
        workflow_manager = MinIOWorkflowManager(config_file)
        
        # 初始化项目
        init_result = workflow_manager.initialize_project()
        if init_result.get("error"):
            logger.error(f"项目初始化失败: {init_result['error']}")
            return
        
        logger.info(f"项目初始化成功: {init_result['message']}")
        
        # 2. 连接Label Studio
        logger.info("连接Label Studio...")
        ls_client = Client(url=label_studio_url, api_key=label_studio_api_key)
        
        # 3. 运行WAV音频工作流
        logger.info("开始WAV音频标注工作流...")
        workflow_result = workflow_manager.run_wav_audio_workflow(
            wav_files_dir=wav_files_dir,
            ls_client=ls_client,
            create_project=True
        )
        
        if workflow_result.get("error"):
            logger.error(f"工作流执行失败: {workflow_result['error']}")
            return
        
        logger.info(f"工作流执行成功: {workflow_result['message']}")
        logger.info(f"结果: {workflow_result['results']}")
        
        # 4. 连接PostgreSQL数据库
        logger.info("连接PostgreSQL数据库...")
        db_connection = psycopg2.connect(**db_config)
        
        # 5. 导出标注数据（假设项目ID为1）
        project_id = workflow_result['results'].get('project_id', 1)
        logger.info(f"导出项目 {project_id} 的标注数据...")
        
        export_result = workflow_manager.export_wav_annotations(
            ls_client=ls_client,
            project_id=project_id,
            db_connection=db_connection
        )
        
        if export_result.get("error"):
            logger.error(f"标注导出失败: {export_result['error']}")
        else:
            logger.info(f"标注导出成功: {export_result['message']}")
            logger.info(f"导出结果: {export_result['export_result']}")
            logger.info(f"数据库结果: {export_result['postgresql_result']}")
        
        # 6. 演示标注数据恢复
        logger.info("演示标注数据恢复...")
        task_id = 1  # 假设任务ID为1
        restore_result = workflow_manager.restore_wav_annotations(
            task_id=task_id,
            db_connection=db_connection
        )
        
        if restore_result.get("error"):
            logger.error(f"标注恢复失败: {restore_result['error']}")
        else:
            logger.info(f"标注恢复成功: {restore_result}")
        
        # 7. 获取工作流配置
        logger.info("获取WAV工作流配置...")
        config_result = workflow_manager.get_wav_workflow_config()
        
        if config_result.get("error"):
            logger.error(f"配置获取失败: {config_result['error']}")
        else:
            logger.info(f"工作流配置: {config_result}")
        
        # 8. 清理资源
        db_connection.close()
        logger.info("数据库连接已关闭")
        
        logger.info("WAV音频标注工作流演示完成！")
        
    except Exception as e:
        logger.error(f"工作流执行过程中发生错误: {str(e)}")
        raise

def create_sample_wav_files():
    """创建示例WAV文件（用于测试）"""
    import wave
    import numpy as np
    
    # 创建示例WAV文件目录
    wav_dir = Path("data/wav_files")
    wav_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成示例WAV文件
    sample_rate = 44100
    duration = 5  # 5秒
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # 生成不同频率的正弦波
    frequencies = [440, 880, 1320]  # A4, A5, E6
    
    for i, freq in enumerate(frequencies):
        # 生成音频数据
        audio_data = np.sin(2 * np.pi * freq * t)
        audio_data = (audio_data * 32767).astype(np.int16)
        
        # 保存为WAV文件
        filename = wav_dir / f"sample_{i+1}_{freq}hz.wav"
        with wave.open(str(filename), 'w') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16位
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        print(f"创建示例WAV文件: {filename}")

def setup_database():
    """设置数据库"""
    import psycopg2
    
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "postgres",  # 连接到默认数据库
        "user": "postgres",
        "password": "postgres"
    }
    
    try:
        # 连接到PostgreSQL
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # 创建音频标注数据库
            cursor.execute("CREATE DATABASE audio_annotations;")
            print("创建数据库: audio_annotations")
            
            # 创建用户
            cursor.execute("CREATE USER audio_user WITH PASSWORD 'audio_password';")
            print("创建用户: audio_user")
            
            # 授权
            cursor.execute("GRANT ALL PRIVILEGES ON DATABASE audio_annotations TO audio_user;")
            print("授权完成")
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"数据库设置失败: {e}")

if __name__ == "__main__":
    print("=== WAV音频标注工作流演示 ===")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            print("设置数据库...")
            setup_database()
        elif sys.argv[1] == "create_samples":
            print("创建示例WAV文件...")
            create_sample_wav_files()
        else:
            print("用法:")
            print("  python wav_audio_workflow_example.py setup          # 设置数据库")
            print("  python wav_audio_workflow_example.py create_samples # 创建示例文件")
            print("  python wav_audio_workflow_example.py                 # 运行完整工作流")
    else:
        # 运行完整工作流
        main()
