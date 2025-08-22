"""
温度标注ML Backend的测试文件

测试各个组件的功能和集成
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# 导入被测试的模块
from model import TemperatureModel
from temperature_predictor import TemperaturePredictor
from prediction import Prediction, start_end_time_1D, convert_to_labelstudio_form
from utils import validate_temperature_data, preprocess_temperature_data, extract_temperature_channels


class TestPrediction:
    """测试预测结果数据结构"""
    
    def test_prediction_creation(self):
        """测试预测结果创建"""
        pred = Prediction("test_group", "test_label", 1.0, 2.0, 0.8)
        
        assert pred.label_group == "test_group"
        assert pred.label == "test_label"
        assert pred.start == 1.0
        assert pred.end == 2.0
        assert pred.score == 0.8
    
    def test_prediction_repr(self):
        """测试预测结果的字符串表示"""
        pred = Prediction("test_group", "test_label", 1.0, 2.0)
        repr_str = repr(pred)
        
        assert "TemperaturePrediction" in repr_str
        assert "test_label" in repr_str
        assert "1.0" in repr_str
        assert "2.0" in repr_str


class TestPredictionFunctions:
    """测试预测函数"""
    
    def test_start_end_time_1D_positive(self):
        """测试正向阈值检测"""
        data = np.array([0, 1, 2, 3, 4, 5])
        threshold = 2.5
        
        intervals = start_end_time_1D(data, threshold, postive=True)
        
        assert len(intervals) == 1
        assert intervals[0] == (3, 5)  # 索引3-5的值大于2.5
    
    def test_start_end_time_1D_negative(self):
        """测试负向阈值检测"""
        data = np.array([5, 4, 3, 2, 1, 0])
        threshold = 2.5
        
        intervals = start_end_time_1D(data, threshold, postive=False)
        
        assert len(intervals) == 1
        assert intervals[0] == (3, 5)  # 索引3-5的值小于2.5
    
    def test_convert_to_labelstudio_form(self):
        """测试转换为Label Studio格式"""
        predictions = [
            Prediction("group1", "label1", 1.0, 2.0),
            Prediction("group2", "label2", 3.0, None)
        ]
        
        result = convert_to_labelstudio_form(predictions, "test_model")
        
        assert len(result) == 1
        assert result[0]["model_version"] == "test_model"
        assert len(result[0]["result"]) == 2
        
        # 检查第一个预测结果
        first_result = result[0]["result"][0]
        assert first_result["from_name"] == "group1"
        assert first_result["to_name"] == "ts"
        assert first_result["type"] == "timeserieslabels"
        assert first_result["value"]["start"] == 1.0
        assert first_result["value"]["end"] == 2.0
        assert first_result["value"]["timeserieslabels"] == ["label1"]
        
        # 检查第二个预测结果（时间点）
        second_result = result[0]["result"][1]
        assert second_result["value"]["start"] == 3.0
        assert second_result["value"]["end"] == 3.0  # 应该自动设置为start


class TestUtils:
    """测试工具函数"""
    
    def test_validate_temperature_data_valid(self):
        """测试有效温度数据验证"""
        df = pd.DataFrame({
            'time': [0, 1, 2, 3],
            'Te_1': [100, 200, 300, 400],
            'Te_2': [150, 250, 350, 450]
        })
        
        assert validate_temperature_data(df) == True
    
    def test_validate_temperature_data_missing_time(self):
        """测试缺少时间列的数据验证"""
        df = pd.DataFrame({
            'Te_1': [100, 200, 300, 400],
            'Te_2': [150, 250, 350, 450]
        })
        
        assert validate_temperature_data(df) == False
    
    def test_validate_temperature_data_empty(self):
        """测试空数据验证"""
        df = pd.DataFrame()
        
        assert validate_temperature_data(df) == False
    
    def test_extract_temperature_channels(self):
        """测试温度通道提取"""
        df = pd.DataFrame({
            'time': [0, 1, 2],
            'Te_1': [100, 200, 300],
            'Te_2': [150, 250, 350],
            'other': [10, 20, 30]
        })
        
        channels = extract_temperature_channels(df)
        
        assert 'Te_1' in channels
        assert 'Te_2' in channels
        assert 'other' not in channels
        assert len(channels) == 2


class TestTemperaturePredictor:
    """测试温度预测器"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.predictor = TemperaturePredictor()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.predictor.label_group == 'temperature_events'
        assert self.predictor.temp_rise_threshold == 1000.0
        assert self.predictor.temp_fall_threshold == 500.0
        assert self.predictor.gradient_threshold == 100.0
    
    def test_extract_temperature_channels(self):
        """测试温度通道提取"""
        df = pd.DataFrame({
            'time': [0, 1, 2],
            'Te_1': [100, 200, 300],
            'Te_2': [150, 250, 350],
            'other': [10, 20, 30]
        })
        
        channels = self.predictor._extract_temperature_channels(df)
        
        assert 'Te_1' in channels
        assert 'Te_2' in channels
        assert 'other' not in channels
    
    def test_handle_missing_values(self):
        """测试缺失值处理"""
        # 创建包含NaN的数据
        temp_data = np.array([100, np.nan, 300, np.nan, 500])
        
        cleaned_data = self.predictor._handle_missing_values(temp_data)
        
        # 检查NaN值是否被处理
        assert not np.any(np.isnan(cleaned_data))
        assert len(cleaned_data) == 5
    
    def test_update_thresholds(self):
        """测试阈值更新"""
        new_thresholds = {
            'temp_rise_threshold': 1200.0,
            'temp_fall_threshold': 600.0
        }
        
        self.predictor.update_thresholds(new_thresholds)
        
        assert self.predictor.temp_rise_threshold == 1200.0
        assert self.predictor.temp_fall_threshold == 600.0
    
    def test_get_current_thresholds(self):
        """测试获取当前阈值"""
        thresholds = self.predictor.get_current_thresholds()
        
        assert 'temp_rise_threshold' in thresholds
        assert 'temp_fall_threshold' in thresholds
        assert 'gradient_threshold' in thresholds
        assert thresholds['temp_rise_threshold'] == 1000.0


class TestTemperatureModel:
    """测试温度标注模型"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with patch('utils.load_data'):
            with patch('utils.validate_temperature_data', return_value=True):
                with patch('utils.preprocess_temperature_data'):
                    self.model = TemperatureModel()
                    self.model.setup()
    
    def test_model_initialization(self):
        """测试模型初始化"""
        assert self.model.get("model_version") == "temperature_v1.0"
        assert hasattr(self.model, 'predictor')
        assert isinstance(self.model.predictor, TemperaturePredictor)
    
    def test_get_model_info(self):
        """测试获取模型信息"""
        info = self.model.get_model_info()
        
        assert 'model_version' in info
        assert 'training_count' in info
        assert 'last_training_time' in info
        assert 'current_thresholds' in info
        assert info['model_version'] == 'temperature_v1.0'
    
    def test_health_check(self):
        """测试健康检查"""
        health = self.model.health_check()
        
        assert 'status' in health
        assert health['status'] == 'healthy'
        assert 'model_version' in health
        assert 'predictor_initialized' in health
    
    def test_reset_model(self):
        """测试模型重置"""
        # 修改一些参数
        self.model.set('training_count', 100)
        
        # 重置模型
        self.model.reset_model()
        
        # 检查是否重置
        assert self.model.get('training_count') == 0
        assert self.model.get('model_version') == 'temperature_v1.0'


class TestIntegration:
    """集成测试"""
    
    def test_end_to_end_prediction(self):
        """测试端到端预测流程"""
        with patch('utils.load_data') as mock_load:
            with patch('utils.validate_temperature_data', return_value=True):
                with patch('utils.preprocess_temperature_data') as mock_preprocess:
                    # 创建模型
                    model = TemperatureModel()
                    model.setup()
                    
                    # 模拟数据
                    test_data = pd.DataFrame({
                        'time': [0, 1, 2, 3, 4],
                        'Te_1': [100, 200, 300, 400, 500],
                        'Te_2': [150, 250, 350, 450, 550]
                    })
                    
                    mock_load.return_value = {123: test_data}
                    mock_preprocess.return_value = test_data
                    
                    # 执行预测
                    tasks = [{'data': {'shot': 123, 'csv': 'test.csv'}}]
                    response = model.predict(tasks)
                    
                    # 验证响应
                    assert hasattr(response, 'predictions')
                    assert isinstance(response.predictions, list)
    
    def test_prediction_with_mock_data(self):
        """测试使用模拟数据的预测"""
        # 创建模拟的预测器
        mock_predictor = Mock()
        mock_predictor.user_predict.return_value = [
            Prediction("test_group", "test_label", 1.0, 2.0)
        ]
        
        # 创建模型并替换预测器
        model = TemperatureModel()
        model.predictor = mock_predictor
        
        # 模拟数据加载
        with patch.object(model, 'get_data') as mock_get_data:
            test_data = pd.DataFrame({
                'time': [0, 1, 2],
                'Te_1': [100, 200, 300]
            })
            mock_get_data.return_value = {123: test_data}
            
            # 执行预测
            tasks = [{'data': {'shot': 123, 'csv': 'test.csv'}}]
            response = model.predict(tasks)
            
            # 验证预测器被调用
            mock_predictor.user_predict.assert_called_once()
            
            # 验证响应
            assert len(response.predictions) > 0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
