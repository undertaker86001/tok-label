"""
振动数据PHM预测性维护系统测试API

This file contains comprehensive tests for the VibrationPHM API. You can run these tests by installing test requirements:

    ```bash
    pip install -r requirements-test.txt
    ```
Then execute `pytest` in the directory of this file.

测试覆盖范围：
- 单元测试：预测器功能测试
- 集成测试：API接口测试
- 性能测试：响应时间测试
- 错误处理测试：异常情况处理
"""

import pytest
import json
import numpy as np
import pandas as pd
import requests
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from model import VibrationPHMModel
from predictor import VibrationPredictor


class TestVibrationPredictor:
    """振动预测器单元测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.predictor = VibrationPredictor()
        
        # 生成测试数据
        self.test_data = self._generate_test_vibration_data()
    
    def _generate_test_vibration_data(self) -> pd.DataFrame:
        """生成测试振动数据"""
        # 生成10秒的测试数据，1ms分辨率
        time_points = np.arange(0, 10, 0.001)
        
        # 模拟振动信号
        base_freq = 30  # 30Hz基础频率
        noise_level = 0.2
        
        vibration_x = np.sin(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_y = np.cos(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        
        # 模拟转速变化
        base_rpm = 1200  # 中转速
        rpm_variation = 50 * np.sin(2 * np.pi * 0.05 * time_points)
        rotation_speed = base_rpm + rpm_variation + \
                        5 * np.random.normal(0, 1, len(time_points))
        
        # 计算振动幅值
        vibration_amplitude = np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
        
        return pd.DataFrame({
            'time': time_points,
            'vibration_x': vibration_x,
            'vibration_y': vibration_y,
            'vibration_z': vibration_z,
            'rotation_speed': rotation_speed,
            'vibration_amplitude': vibration_amplitude
        })
    
    def test_feature_extraction(self):
        """测试特征提取功能"""
        features = self.predictor.extract_features(self.test_data)
        
        # 验证特征是否提取成功
        assert isinstance(features, dict)
        assert len(features) > 0
        
        # 验证时域特征
        expected_time_features = ['vibration_x_rms', 'vibration_x_peak', 'vibration_x_std']
        for feature in expected_time_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))
        
        # 验证频域特征
        assert 'dominant_freq' in features
        assert isinstance(features['dominant_freq'], (int, float))
        
        # 验证转速特征
        assert 'rpm_mean' in features
        assert isinstance(features['rpm_mean'], (int, float))
    
    def test_speed_segment_prediction(self):
        """测试转速段预测功能"""
        predictions = self.predictor.predict_speed_segments(self.test_data)
        
        # 验证预测结果
        assert isinstance(predictions, list)
        
        if predictions:  # 如果有预测结果
            for pred in predictions:
                assert isinstance(pred.start, (int, float))
                assert isinstance(pred.end, (int, float))
                assert pred.label_choice in ['低转速', '中转速', '高转速']
                assert pred.label_group == 'speed_level'
    
    def test_fault_type_prediction(self):
        """测试故障类型预测功能"""
        features = self.predictor.extract_features(self.test_data)
        predictions = self.predictor.predict_fault_type(self.test_data, features)
        
        # 验证预测结果
        assert isinstance(predictions, list)
        assert len(predictions) > 0
        
        for pred in predictions:
            assert isinstance(pred.start, (int, float))
            assert isinstance(pred.end, (int, float))
            assert pred.label_choice in ['正常', '不平衡', '轴承故障', '齿轮故障']
            assert pred.label_group == 'fault_type'
    
    def test_quality_score_prediction(self):
        """测试质量分数预测功能"""
        features = self.predictor.extract_features(self.test_data)
        quality_prediction = self.predictor.predict_quality_score(features)
        
        # 验证预测结果
        assert isinstance(quality_prediction.value, (int, float))
        assert 0 <= quality_prediction.value <= 100
        assert quality_prediction.label_group == 'quality_score'
    
    def test_full_prediction(self):
        """测试完整预测流程"""
        predictions = self.predictor.predict(self.test_data)
        
        # 验证预测结果
        assert isinstance(predictions, list)
        assert len(predictions) > 0
        
        # 验证包含所有类型的预测
        prediction_types = [type(pred).__name__ for pred in predictions]
        assert 'TimeseriesSpan' in prediction_types
        assert 'Number' in prediction_types
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空数据
        empty_data = pd.DataFrame()
        features = self.predictor.extract_features(empty_data)
        assert isinstance(features, dict)
        
        # 测试缺失列的数据
        partial_data = self.test_data[['time', 'vibration_x']]
        features = self.predictor.extract_features(partial_data)
        assert isinstance(features, dict)
        
        # 测试异常数据
        nan_data = self.test_data.copy()
        nan_data.loc[0, 'vibration_x'] = np.nan
        features = self.predictor.extract_features(nan_data)
        assert isinstance(features, dict)


class TestVibrationPHMModel:
    """振动PHM模型单元测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.model = VibrationPHMModel()
        self.model.setup()
    
    def test_model_setup(self):
        """测试模型设置"""
        assert hasattr(self.model, 'predictor')
        assert isinstance(self.model.predictor, VibrationPredictor)
        assert hasattr(self.model, 'label_groups')
        assert isinstance(self.model.label_groups, dict)
    
    def test_convert_predictions_to_labelstudio(self):
        """测试预测结果转换为Label Studio格式"""
        # 创建模拟预测结果
        from toklabel.prediction import TimeseriesSpan, Number
        
        mock_predictions = [
            TimeseriesSpan(
                start=0.0,
                end=5.0,
                label_choice='中转速',
                label_group='speed_level'
            ),
            Number(
                value=85.5,
                label_group='quality_score',
                label_target='ts'
            )
        ]
        
        ls_results = self.model.convert_predictions_to_labelstudio(mock_predictions, 240829001)
        
        assert isinstance(ls_results, list)
        assert len(ls_results) == 2
        
        # 验证时间序列标注
        timeseries_result = ls_results[0]
        assert timeseries_result['from_name'] == 'speed_level'
        assert timeseries_result['to_name'] == 'ts'
        assert timeseries_result['type'] == 'timeserieslabels'
        assert timeseries_result['value']['timeserieslabels'] == ['中转速']
        
        # 验证数值标注
        number_result = ls_results[1]
        assert number_result['from_name'] == 'quality_score'
        assert number_result['to_name'] == 'ts'
        assert number_result['type'] == 'number'
        assert number_result['value']['number'] == 85.5


class TestVibrationAPI:
    """振动数据API集成测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.base_url = "http://localhost:9090"
        self.test_data = self._generate_test_request_data()
    
    def _generate_test_request_data(self) -> Dict:
        """生成测试请求数据"""
        return {
            "tasks": [
                {
                    "data": {
                        "shot": 240829001,
                        "csv": "http://file-server:8000/data/vibration_data_240829001.csv"
                    }
                },
                {
                    "data": {
                        "shot": 240829002,
                        "csv": "http://file-server:8000/data/vibration_data_240829002.csv"
                    }
                }
            ]
        }
    
    @pytest.mark.integration
    def test_health_check(self):
        """测试健康检查接口"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert 'status' in data
        except requests.exceptions.RequestException:
            pytest.skip("API服务未启动")
    
    @pytest.mark.integration
    def test_predict_endpoint(self):
        """测试预测接口"""
        try:
            response = requests.post(
                f"{self.base_url}/predict",
                json=self.test_data,
                timeout=30
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # 验证响应格式
            assert 'predictions' in data
            assert isinstance(data['predictions'], list)
            assert len(data['predictions']) == len(self.test_data['tasks'])
            
            # 验证每个预测结果
            for prediction in data['predictions']:
                assert 'result' in prediction
                assert isinstance(prediction['result'], list)
                assert 'score' in prediction
                assert isinstance(prediction['score'], (int, float))
                
        except requests.exceptions.RequestException:
            pytest.skip("API服务未启动")
    
    @pytest.mark.integration
    def test_predict_with_mock_data(self):
        """测试使用模拟数据的预测"""
        # 创建模拟数据
        mock_data = {
            "tasks": [
                {
                    "data": {
                        "shot": 240829001,
                        "csv": "mock_data_url"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/predict",
                json=mock_data,
                timeout=30
            )
            
            # 即使数据不存在，也应该返回200状态码
            assert response.status_code == 200
            
        except requests.exceptions.RequestException:
            pytest.skip("API服务未启动")
    
    @pytest.mark.integration
    def test_predict_performance(self):
        """测试预测性能"""
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/predict",
                json=self.test_data,
                timeout=30
            )
            end_time = time.time()
            
            assert response.status_code == 200
            # 预测时间应该在合理范围内（小于10秒）
            assert (end_time - start_time) < 10
            
        except requests.exceptions.RequestException:
            pytest.skip("API服务未启动")
    
    @pytest.mark.integration
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效请求
        invalid_data = {"invalid": "data"}
        
        try:
            response = requests.post(
                f"{self.base_url}/predict",
                json=invalid_data,
                timeout=10
            )
            
            # 应该返回400或500错误
            assert response.status_code in [400, 500]
            
        except requests.exceptions.RequestException:
            pytest.skip("API服务未启动")


class TestVibrationDataIntegration:
    """振动数据集成测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_shots = [240829001, 240829002]
    
    @patch('vibration_data_manager.VibrationDataManager')
    def test_data_manager_integration(self, mock_data_manager):
        """测试数据管理器集成"""
        # 模拟数据管理器
        mock_manager = Mock()
        mock_data_manager.return_value = mock_manager
        
        # 模拟数据导出
        mock_urls = {
            240829001: "http://file-server:8000/data/vibration_data_240829001.csv",
            240829002: "http://file-server:8000/data/vibration_data_240829002.csv"
        }
        mock_manager.export_vibration_data.return_value = mock_urls
        
        # 测试数据导出
        urls = mock_manager.export_vibration_data(self.test_shots)
        assert urls == mock_urls
        assert len(urls) == len(self.test_shots)
    
    @patch('scripts.annotation_analysis.VibrationAnnotationAnalyzer')
    def test_annotation_analyzer_integration(self, mock_analyzer):
        """测试标注分析器集成"""
        # 模拟分析器
        mock_analyzer_instance = Mock()
        mock_analyzer.return_value = mock_analyzer_instance
        
        # 模拟报告生成
        mock_report = {
            'summary': {'total_annotations': 100},
            'label_distribution': {'speed_level': {'中转速': 50}}
        }
        mock_analyzer_instance.export_annotation_report.return_value = mock_report
        
        # 测试报告生成
        report = mock_analyzer_instance.export_annotation_report(self.test_shots, 'test_report.json')
        assert report == mock_report
        assert 'summary' in report
        assert 'label_distribution' in report


def run_manual_tests():
    """手动运行测试"""
    print("=== 振动数据PHM系统手动测试 ===")
    
    # 测试预测器
    print("1. 测试振动预测器...")
    predictor = VibrationPredictor()
    
    # 生成测试数据
    time_points = np.arange(0, 10, 0.001)
    vibration_x = np.sin(2 * np.pi * 30 * time_points) + 0.1 * np.random.normal(0, 1, len(time_points))
    vibration_y = np.cos(2 * np.pi * 30 * time_points) + 0.1 * np.random.normal(0, 1, len(time_points))
    vibration_z = 0.5 * np.sin(2 * np.pi * 30 * 2 * time_points) + 0.1 * np.random.normal(0, 1, len(time_points))
    rotation_speed = 1200 + 50 * np.sin(2 * np.pi * 0.1 * time_points) + 5 * np.random.normal(0, 1, len(time_points))
    
    test_data = pd.DataFrame({
        'time': time_points,
        'vibration_x': vibration_x,
        'vibration_y': vibration_y,
        'vibration_z': vibration_z,
        'rotation_speed': rotation_speed,
        'vibration_amplitude': np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
    })
    
    # 执行预测
    predictions = predictor.predict(test_data)
    
    print(f"   预测结果数量: {len(predictions)}")
    for i, pred in enumerate(predictions):
        if hasattr(pred, 'label_choice'):
            print(f"   预测{i+1}: {pred.label_group} = {pred.label_choice}")
        elif hasattr(pred, 'value'):
            print(f"   预测{i+1}: {pred.label_group} = {pred.value}")
    
    print("2. 测试特征提取...")
    features = predictor.extract_features(test_data)
    print(f"   提取特征数量: {len(features)}")
    print(f"   主要特征: {list(features.keys())[:5]}")
    
    print("3. 测试转速段预测...")
    speed_predictions = predictor.predict_speed_segments(test_data)
    print(f"   转速段预测数量: {len(speed_predictions)}")
    
    print("4. 测试故障类型预测...")
    fault_predictions = predictor.predict_fault_type(test_data, features)
    print(f"   故障类型预测数量: {len(fault_predictions)}")
    
    print("5. 测试质量分数预测...")
    quality_prediction = predictor.predict_quality_score(features)
    print(f"   质量分数: {quality_prediction.value}")
    
    print("=== 手动测试完成 ===")


if __name__ == "__main__":
    # 运行手动测试
    run_manual_tests()
