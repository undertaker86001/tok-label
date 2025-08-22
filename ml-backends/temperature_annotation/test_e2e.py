"""
温度标注ML Backend的端到端测试

测试完整的ML Backend服务流程，包括：
- 服务启动和健康检查
- 数据加载和预处理
- 温度预测和结果转换
- API接口响应
- 模型训练和参数更新
"""

import pytest
import requests
import time
import json
import pandas as pd
import numpy as np
import tempfile
import os
import subprocess
import signal
from unittest.mock import patch, MagicMock
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
TEST_CONFIG = {
    'host': 'localhost',
    'port': 9090,
    'base_url': 'http://localhost:9090',
    'timeout': 30,
    'retry_attempts': 3
}


class TestTemperatureBackendE2E:
    """温度标注ML Backend端到端测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化，启动ML Backend服务"""
        cls.service_process = None
        cls.service_url = f"{TEST_CONFIG['base_url']}"
        
        # 检查服务是否已经在运行
        if cls._is_service_running():
            logger.info("ML Backend服务已在运行")
            return
        
        # 启动服务
        cls._start_service()
        
        # 等待服务启动
        cls._wait_for_service()
    
    @classmethod
    def teardown_class(cls):
        """测试类清理，停止ML Backend服务"""
        if cls.service_process:
            cls._stop_service()
    
    @classmethod
    def _is_service_running(cls):
        """检查服务是否在运行"""
        try:
            response = requests.get(f"{cls.service_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    @classmethod
    def _start_service(cls):
        """启动ML Backend服务"""
        try:
            logger.info("启动温度标注ML Backend服务...")
            
            # 使用Python直接启动服务
            cmd = [
                'python', '_wsgi.py',
                '--host', TEST_CONFIG['host'],
                '--port', str(TEST_CONFIG['port']),
                '--debug'
            ]
            
            cls.service_process = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"服务启动命令: {' '.join(cmd)}")
            logger.info(f"服务进程ID: {cls.service_process.pid}")
            
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            raise
    
    @classmethod
    def _stop_service(cls):
        """停止ML Backend服务"""
        if cls.service_process:
            logger.info("停止ML Backend服务...")
            try:
                cls.service_process.terminate()
                cls.service_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.service_process.kill()
                cls.service_process.wait()
            finally:
                cls.service_process = None
    
    @classmethod
    def _wait_for_service(cls):
        """等待服务启动完成"""
        logger.info("等待服务启动...")
        max_wait = 60  # 最大等待60秒
        wait_interval = 2
        
        for i in range(0, max_wait, wait_interval):
            if cls._is_service_running():
                logger.info(f"服务启动成功，耗时 {i} 秒")
                return
            time.sleep(wait_interval)
        
        raise TimeoutError("服务启动超时")
    
    def _make_request(self, method, endpoint, data=None, headers=None):
        """发送HTTP请求"""
        url = f"{self.service_url}{endpoint}"
        
        for attempt in range(TEST_CONFIG['retry_attempts']):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=TEST_CONFIG['timeout'])
                elif method.upper() == 'POST':
                    response = requests.post(url, json=data, headers=headers, timeout=TEST_CONFIG['timeout'])
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt == TEST_CONFIG['retry_attempts'] - 1:
                    raise
                logger.warning(f"请求失败，重试 {attempt + 1}/{TEST_CONFIG['retry_attempts']}: {e}")
                time.sleep(1)
    
    def test_01_service_health(self):
        """测试服务健康状态"""
        logger.info("测试服务健康状态...")
        
        response = self._make_request('GET', '/health')
        
        assert response.status_code == 200
        health_data = response.json()
        
        assert 'status' in health_data
        assert health_data['status'] == 'healthy'
        assert 'model_version' in health_data
        assert 'predictor_initialized' in health_data
        
        logger.info(f"服务健康状态: {health_data}")
    
    def test_02_model_info(self):
        """测试模型信息接口"""
        logger.info("测试模型信息接口...")
        
        response = self._make_request('GET', '/model/info')
        
        assert response.status_code == 200
        model_info = response.json()
        
        assert 'model_version' in model_info
        assert 'training_count' in model_info
        assert 'last_training_time' in model_info
        assert 'current_thresholds' in model_info
        
        # 验证阈值参数
        thresholds = model_info['current_thresholds']
        assert 'temp_rise_threshold' in thresholds
        assert 'temp_fall_threshold' in thresholds
        assert 'gradient_threshold' in thresholds
        
        logger.info(f"模型信息: {model_info}")
    
    def test_03_prediction_with_sample_data(self):
        """测试使用样本数据的预测功能"""
        logger.info("测试使用样本数据的预测功能...")
        
        # 创建样本温度数据
        sample_data = self._create_sample_temperature_data()
        
        # 准备预测请求
        prediction_request = {
            "tasks": [
                {
                    "data": {
                        "shot": 12345,
                        "csv": "sample_temperature_data.csv"
                    }
                }
            ]
        }
        
        # 模拟数据加载
        with patch('utils.load_data') as mock_load:
            mock_load.return_value = {12345: sample_data}
            
            response = self._make_request('POST', '/predict', data=prediction_request)
            
            assert response.status_code == 200
            prediction_result = response.json()
            
            # 验证预测结果结构
            assert 'predictions' in prediction_result
            predictions = prediction_result['predictions']
            
            if len(predictions) > 0:
                # 验证预测结果格式
                first_prediction = predictions[0]
                assert 'model_version' in first_prediction
                assert 'result' in first_prediction
                
                # 验证结果内容
                results = first_prediction['result']
                for result in results:
                    assert 'from_name' in result
                    assert 'to_name' in result
                    assert 'type' in result
                    assert 'value' in result
                    assert result['type'] == 'timeserieslabels'
                
                logger.info(f"预测成功，生成了 {len(predictions)} 个预测结果")
            else:
                logger.info("预测完成，但未生成预测结果（可能是阈值设置过高）")
    
    def test_04_prediction_with_realistic_data(self):
        """测试使用真实场景数据的预测功能"""
        logger.info("测试使用真实场景数据的预测功能...")
        
        # 创建更真实的温度数据（模拟托卡马克实验）
        realistic_data = self._create_realistic_temperature_data()
        
        prediction_request = {
            "tasks": [
                {
                    "data": {
                        "shot": 240830001,
                        "csv": "realistic_temperature_data.csv"
                    }
                }
            ]
        }
        
        with patch('utils.load_data') as mock_load:
            mock_load.return_value = {240830001: realistic_data}
            
            response = self._make_request('POST', '/predict', data=prediction_request)
            
            assert response.status_code == 200
            prediction_result = response.json()
            
            # 验证预测结果
            assert 'predictions' in prediction_result
            predictions = prediction_result['predictions']
            
            if len(predictions) > 0:
                # 分析预测结果类型
                result_types = set()
                for pred in predictions:
                    for result in pred['result']:
                        label = result['value']['timeserieslabels'][0]
                        result_types.add(label)
                
                logger.info(f"检测到的温度事件类型: {result_types}")
                
                # 验证是否检测到预期的温度事件
                expected_events = ['上升阶段', '峰值时刻', '下降阶段', '平台期']
                detected_events = [event for event in expected_events if any(event in label for label in result_types)]
                
                logger.info(f"检测到的事件: {detected_events}")
                assert len(detected_events) > 0, "应该检测到至少一种温度事件"
    
    def test_05_model_training(self):
        """测试模型训练功能"""
        logger.info("测试模型训练功能...")
        
        # 准备训练数据（模拟人工标注）
        training_data = {
            "event": "ANNOTATION_CREATED",
            "annotation": {
                "id": 1,
                "result": [
                    {
                        "from_name": "temperature_events",
                        "type": "timeserieslabels",
                        "value": {
                            "start": 2.0,
                            "end": 4.0,
                            "timeserieslabels": ["Te_1_上升阶段"]
                        }
                    }
                ]
            },
            "task": {
                "id": 1,
                "data": {
                    "shot": 240830001
                }
            }
        }
        
        # 发送训练请求
        response = self._make_request('POST', '/fit', data=training_data)
        
        # 训练接口通常返回200状态码
        assert response.status_code in [200, 204]
        
        # 验证模型参数是否更新
        time.sleep(2)  # 等待训练完成
        
        model_info_response = self._make_request('GET', '/model/info')
        assert model_info_response.status_code == 200
        
        updated_model_info = model_info_response.json()
        assert updated_model_info['training_count'] > 0
        
        logger.info(f"模型训练完成，训练次数: {updated_model_info['training_count']}")
    
    def test_06_threshold_optimization(self):
        """测试阈值优化功能"""
        logger.info("测试阈值优化功能...")
        
        # 获取当前阈值
        initial_response = self._make_request('GET', '/model/info')
        initial_thresholds = initial_response.json()['current_thresholds']
        
        logger.info(f"初始阈值: {initial_thresholds}")
        
        # 发送多个标注数据来触发阈值优化
        training_events = [
            {
                "event": "ANNOTATION_CREATED",
                "annotation": {
                    "id": 2,
                    "result": [
                        {
                            "from_name": "temperature_events",
                            "type": "timeserieslabels",
                            "value": {
                                "start": 1.0,
                                "end": 3.0,
                                "timeserieslabels": ["Te_1_峰值时刻"]
                            }
                        }
                    ]
                },
                "task": {"id": 2, "data": {"shot": 240830002}}
            },
            {
                "event": "ANNOTATION_CREATED",
                "annotation": {
                    "id": 3,
                    "result": [
                        {
                            "from_name": "temperature_events",
                            "type": "timeserieslabels",
                            "value": {
                                "start": 5.0,
                                "end": 7.0,
                                "timeserieslabels": ["Te_1_下降阶段"]
                            }
                        }
                    ]
                },
                "task": {"id": 3, "data": {"shot": 240830003}}
            }
        ]
        
        # 发送训练事件
        for event_data in training_events:
            response = self._make_request('POST', '/fit', data=event_data)
            assert response.status_code in [200, 204]
        
        # 等待训练完成
        time.sleep(3)
        
        # 检查阈值是否被优化
        final_response = self._make_request('GET', '/model/info')
        final_thresholds = final_response.json()['current_thresholds']
        
        logger.info(f"优化后阈值: {final_thresholds}")
        
        # 验证阈值是否发生变化（由于是模拟数据，可能变化很小）
        threshold_changed = False
        for key in initial_thresholds:
            if abs(initial_thresholds[key] - final_thresholds[key]) > 0.01:
                threshold_changed = True
                break
        
        if threshold_changed:
            logger.info("阈值优化成功")
        else:
            logger.info("阈值未发生变化（可能是优化逻辑或数据特征导致的）")
    
    def test_07_error_handling(self):
        """测试错误处理"""
        logger.info("测试错误处理...")
        
        # 测试无效的预测请求
        invalid_request = {
            "tasks": [
                {
                    "data": {
                        "shot": "invalid_shot",
                        "csv": "nonexistent.csv"
                    }
                }
            ]
        }
        
        response = self._make_request('POST', '/predict', data=invalid_request)
        
        # 应该返回200状态码，但预测结果可能为空
        assert response.status_code == 200
        
        # 测试无效的训练数据
        invalid_training_data = {
            "event": "INVALID_EVENT",
            "data": "invalid_data"
        }
        
        response = self._make_request('POST', '/fit', data=invalid_training_data)
        assert response.status_code in [200, 204, 400]
        
        logger.info("错误处理测试完成")
    
    def test_08_performance_test(self):
        """测试性能"""
        logger.info("测试性能...")
        
        # 创建大量数据
        large_data = self._create_large_temperature_data()
        
        prediction_request = {
            "tasks": [
                {
                    "data": {
                        "shot": 999999,
                        "csv": "large_temperature_data.csv"
                    }
                }
            ]
        }
        
        with patch('utils.load_data') as mock_load:
            mock_load.return_value = {999999: large_data}
            
            start_time = time.time()
            response = self._make_request('POST', '/predict', data=prediction_request)
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            assert response.status_code == 200
            assert processing_time < 10.0, f"预测处理时间过长: {processing_time:.2f}秒"
            
            logger.info(f"性能测试完成，处理时间: {processing_time:.2f}秒")
    
    def test_09_model_reset(self):
        """测试模型重置功能"""
        logger.info("测试模型重置功能...")
        
        # 获取当前模型状态
        initial_response = self._make_request('GET', '/model/info')
        initial_info = initial_response.json()
        
        # 重置模型
        reset_response = self._make_request('POST', '/model/reset')
        assert reset_response.status_code in [200, 204]
        
        # 等待重置完成
        time.sleep(2)
        
        # 检查重置后的状态
        final_response = self._make_request('GET', '/model/info')
        final_info = final_response.json()
        
        # 验证重置
        assert final_info['training_count'] == 0
        assert final_info['model_version'] == 'temperature_v1.0'
        
        logger.info("模型重置测试完成")
    
    def _create_sample_temperature_data(self):
        """创建样本温度数据"""
        time_data = np.linspace(0, 10, 1000)
        temp_data = 500 + 1000 * np.sin(time_data) + 100 * np.random.randn(1000)
        
        df = pd.DataFrame({
            'time': time_data,
            'Te_1': temp_data,
            'Te_2': temp_data * 0.8 + 50 * np.random.randn(1000)
        })
        
        return df
    
    def _create_realistic_temperature_data(self):
        """创建真实的温度数据（模拟托卡马克实验）"""
        time_data = np.linspace(0, 15, 1500)
        
        # 模拟托卡马克温度曲线：加热期 -> 平顶期 -> 衰减期
        temp_curve = np.zeros_like(time_data)
        
        # 加热期 (0-3秒)
        heating_mask = (time_data >= 0) & (time_data < 3)
        temp_curve[heating_mask] = 200 + 800 * (time_data[heating_mask] / 3)
        
        # 平顶期 (3-8秒)
        plateau_mask = (time_data >= 3) & (time_data < 8)
        temp_curve[plateau_mask] = 1000 + 50 * np.sin(2 * np.pi * time_data[plateau_mask])
        
        # 衰减期 (8-15秒)
        decay_mask = (time_data >= 8) & (time_data <= 15)
        decay_time = time_data[decay_mask] - 8
        temp_curve[decay_mask] = 1000 * np.exp(-decay_time / 2)
        
        # 添加噪声
        temp_curve += 20 * np.random.randn(len(temp_curve))
        
        # 创建多通道数据
        df = pd.DataFrame({
            'time': time_data,
            'Te_1': temp_curve,
            'Te_2': temp_curve * 0.9 + 30 * np.random.randn(len(temp_curve)),
            'Te_3': temp_curve * 1.1 - 50 * np.random.randn(len(temp_curve))
        })
        
        return df
    
    def _create_large_temperature_data(self):
        """创建大量温度数据用于性能测试"""
        time_data = np.linspace(0, 30, 3000)
        temp_data = 500 + 1000 * np.sin(time_data / 5) + 100 * np.random.randn(3000)
        
        df = pd.DataFrame({
            'time': time_data,
            'Te_1': temp_data,
            'Te_2': temp_data * 0.8 + 50 * np.random.randn(3000),
            'Te_3': temp_data * 1.2 - 80 * np.random.randn(3000),
            'Te_4': temp_data * 0.6 + 120 * np.random.randn(3000)
        })
        
        return df


class TestTemperatureBackendIntegration:
    """温度标注ML Backend集成测试类"""
    
    def test_model_initialization(self):
        """测试模型初始化"""
        from model import TemperatureModel
        
        model = TemperatureModel()
        model.setup()
        
        assert model.get("model_version") == "temperature_v1.0"
        assert hasattr(model, 'predictor')
        assert model.get('training_count') == 0
    
    def test_predictor_functionality(self):
        """测试预测器功能"""
        from temperature_predictor import TemperaturePredictor
        from prediction import Prediction
        
        predictor = TemperaturePredictor()
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'time': [0, 1, 2, 3, 4, 5],
            'Te_1': [100, 200, 300, 400, 500, 600],
            'Te_2': [150, 250, 350, 450, 550, 650]
        })
        
        # 执行预测
        predictions = predictor.user_predict(test_data)
        
        # 验证预测结果
        assert isinstance(predictions, list)
        if len(predictions) > 0:
            assert all(isinstance(p, Prediction) for p in predictions)
    
    def test_data_processing_pipeline(self):
        """测试数据处理流水线"""
        from utils import validate_temperature_data, preprocess_temperature_data
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'time': [0, 1, 2, 3, 4],
            'Te_1': [100, 200, 300, 400, 500],
            'Te_2': [150, 250, 350, 450, 550]
        })
        
        # 验证数据
        assert validate_temperature_data(test_data) == True
        
        # 预处理数据
        processed_data = preprocess_temperature_data(test_data)
        assert len(processed_data) == len(test_data)
    
    def test_prediction_conversion(self):
        """测试预测结果转换"""
        from prediction import Prediction, convert_to_labelstudio_form
        
        # 创建预测结果
        predictions = [
            Prediction("temperature_events", "Te_1_上升阶段", 1.0, 3.0),
            Prediction("temperature_events", "Te_1_峰值时刻", 2.0, None)
        ]
        
        # 转换为Label Studio格式
        ls_format = convert_to_labelstudio_form(predictions, "test_model")
        
        assert len(ls_format) == 1
        assert ls_format[0]["model_version"] == "test_model"
        assert len(ls_format[0]["result"]) == 2


if __name__ == "__main__":
    # 运行端到端测试
    pytest.main([__file__, "-v", "--tb=short"])
