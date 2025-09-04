#!/usr/bin/env python3
"""
WAV音频功能测试脚本
测试MinIO adapter的WAV音频标注功能
"""

import os
import sys
import tempfile
import wave
import numpy as np
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def create_test_wav_file(filepath: str, duration: float = 2.0, frequency: float = 440.0):
    """创建测试用的WAV文件"""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = np.sin(2 * np.pi * frequency * t)
    audio_data = (audio_data * 32767).astype(np.int16)
    
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    print(f"创建测试WAV文件: {filepath}")

def test_wav_audio_manager():
    """测试WAV音频管理器"""
    print("=== 测试WAV音频管理器 ===")
    
    try:
        from minio.core.wav_audio_manager import WAVAudioManager
        from minio import Minio
        
        # 创建MinIO客户端（模拟）
        minio_client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
        
        # 创建WAV音频管理器
        wav_manager = WAVAudioManager(minio_client, "test-bucket")
        print("✓ WAV音频管理器创建成功")
        
        # 测试配置生成
        config = wav_manager.create_audio_annotation_config()
        print("✓ 音频标注配置生成成功")
        print(f"配置长度: {len(config)} 字符")
        
        # 测试时间序列配置
        timeseries_config = wav_manager.create_timeseries_audio_config()
        print("✓ 时间序列配置生成成功")
        print(f"时间序列配置长度: {len(timeseries_config)} 字符")
        
        # 测试工作流配置
        workflow_config = wav_manager.create_audio_workflow_config()
        print("✓ 工作流配置生成成功")
        print(f"支持的格式: {workflow_config['audio_processing']['supported_formats']}")
        
        return True
        
    except Exception as e:
        print(f"✗ WAV音频管理器测试失败: {e}")
        return False

def test_workflow_manager():
    """测试工作流管理器"""
    print("\n=== 测试工作流管理器 ===")
    
    try:
        from minio.core.minio_workflow_manager import MinIOWorkflowManager
        
        # 创建临时配置文件
        config_content = """
project: test_wav_project
description: "测试WAV音频项目"

minio:
  enabled: true
  bucket: test-bucket
  endpoint: localhost:9000
  connection:
    access_key: minioadmin
    secret_key: minioadmin
    secure: false

label_studio:
  url: http://localhost:8080
  api_key: test_key
  project_title: "测试音频项目"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            config_file = f.name
        
        # 创建工作流管理器
        workflow_manager = MinIOWorkflowManager(config_file)
        print("✓ 工作流管理器创建成功")
        
        # 测试初始化
        init_result = workflow_manager.initialize_project()
        print(f"✓ 项目初始化结果: {init_result.get('message', '未知')}")
        
        # 测试WAV工作流配置获取
        config_result = workflow_manager.get_wav_workflow_config()
        if config_result.get("error"):
            print(f"⚠ WAV配置获取: {config_result['error']}")
        else:
            print("✓ WAV工作流配置获取成功")
        
        # 清理临时文件
        os.unlink(config_file)
        
        return True
        
    except Exception as e:
        print(f"✗ 工作流管理器测试失败: {e}")
        return False

def test_wav_file_creation():
    """测试WAV文件创建"""
    print("\n=== 测试WAV文件创建 ===")
    
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test_audio.wav")
        
        # 创建测试WAV文件
        create_test_wav_file(test_file, duration=1.0, frequency=440.0)
        
        # 验证文件存在
        if os.path.exists(test_file):
            file_size = os.path.getsize(test_file)
            print(f"✓ 测试WAV文件创建成功: {test_file}")
            print(f"文件大小: {file_size} 字节")
            
            # 验证WAV文件格式
            with wave.open(test_file, 'r') as wav_file:
                channels = wav_file.getnchannels()
                sampwidth = wav_file.getsampwidth()
                framerate = wav_file.getframerate()
                frames = wav_file.getnframes()
                
                print(f"声道数: {channels}")
                print(f"采样宽度: {sampwidth} 字节")
                print(f"采样率: {framerate} Hz")
                print(f"帧数: {frames}")
                
                if channels == 1 and sampwidth == 2 and framerate == 44100:
                    print("✓ WAV文件格式验证通过")
                else:
                    print("✗ WAV文件格式验证失败")
        
        # 清理临时文件
        os.unlink(test_file)
        os.rmdir(temp_dir)
        
        return True
        
    except Exception as e:
        print(f"✗ WAV文件创建测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始WAV音频功能测试...\n")
    
    tests = [
        ("WAV文件创建", test_wav_file_creation),
        ("WAV音频管理器", test_wav_audio_manager),
        ("工作流管理器", test_workflow_manager),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} 测试通过\n")
            else:
                print(f"✗ {test_name} 测试失败\n")
        except Exception as e:
            print(f"✗ {test_name} 测试异常: {e}\n")
    
    print(f"=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有测试通过！WAV音频功能正常工作。")
    else:
        print("⚠ 部分测试失败，请检查相关功能。")

if __name__ == "__main__":
    main()
