#!/usr/bin/env python3
"""
MinIO集成包测试脚本
"""

import sys
import os
import tempfile
import yaml
import pandas as pd

def test_basic_imports():
    """测试基本导入"""
    print("测试基本导入...")
    try:
        from minio import MinIODataManager, MinIOConfigManager, MinIOMonitor
        print("✓ 基本类导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False

def test_config_manager():
    """测试配置管理器"""
    print("测试配置管理器...")
    try:
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_content = """
project: test_project
minio:
  enabled: false
"""
            f.write(config_content)
            config_file = f.name
        
        config_manager = MinIOConfigManager(config_file)
        
        # 测试启用MinIO
        result = config_manager.enable_minio(
            bucket='test-bucket',
            minio_config={
                'endpoint': 'localhost:9000',
                'access_key': 'test',
                'secret_key': 'test'
            }
        )
        
        if result.get("error"):
            print(f"✗ 启用MinIO失败: {result['error']}")
            return False
        
        print("✓ 配置管理器测试成功")
        
        # 清理
        os.unlink(config_file)
        return True
        
    except Exception as e:
        print(f"✗ 配置管理器测试失败: {e}")
        return False

def test_data_manager():
    """测试数据管理器"""
    print("测试数据管理器...")
    try:
        data_manager = MinIODataManager('test_project', bucket='test-bucket')
        
        # 测试创建处理器
        processor = data_manager._create_processor({
            'type': 'filter',
            'config': {'condition': 'time > 0'}
        })
        
        if processor is None:
            print("✗ 处理器创建失败")
            return False
        
        # 测试数据处理
        test_df = pd.DataFrame({'time': [0, 1, 2], 'value': [10, 20, 30]})
        result_df = processor(test_df)
        
        if result_df is None or len(result_df) != 2:
            print("✗ 数据处理失败")
            return False
        
        print("✓ 数据管理器测试成功")
        return True
        
    except Exception as e:
        print(f"✗ 数据管理器测试失败: {e}")
        return False

def test_monitor():
    """测试监控器"""
    print("测试监控器...")
    try:
        monitor = MinIOMonitor('test-bucket')
        
        # 测试健康检查（不连接实际MinIO）
        health_result = monitor.health_check()
        
        # 健康检查应该返回错误状态，因为MinIO未连接
        if health_result["status"] == "error":
            print("✓ 监控器健康检查正确检测到连接错误")
            return True
        else:
            print("✗ 监控器健康检查未正确检测到连接错误")
            return False
        
    except Exception as e:
        print(f"✗ 监控器测试失败: {e}")
        return False

def test_performance_optimizer():
    """测试性能优化器"""
    print("测试性能优化器...")
    try:
        optimizer = MinIOPerformanceOptimizer('test-bucket', max_workers=5)
        
        # 测试缓存统计
        cache_stats = optimizer.get_cache_stats()
        if cache_stats["cached_files"] != 0:
            print("✗ 缓存统计错误")
            return False
        
        # 测试缓存清理
        optimizer.clear_cache()
        cache_stats_after = optimizer.get_cache_stats()
        if cache_stats_after["cached_files"] != 0:
            print("✗ 缓存清理失败")
            return False
        
        print("✓ 性能优化器测试成功")
        return True
        
    except Exception as e:
        print(f"✗ 性能优化器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=== MinIO集成包测试 ===")
    print()
    
    tests = [
        test_basic_imports,
        test_config_manager,
        test_data_manager,
        test_monitor,
        test_performance_optimizer
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 测试异常: {e}")
        print()
    
    print(f"=== 测试结果: {passed}/{total} 通过 ===")
    
    if passed == total:
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
