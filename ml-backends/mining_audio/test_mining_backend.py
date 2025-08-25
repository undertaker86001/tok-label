"""
矿业声音ML Backend的测试文件

测试各个组件的功能和集成
"""

import pytest
import numpy as np
import torch
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# 导入被测试的模块
from model import MiningAudioMLBackend, AudioFeatureExtractor, MiningAudioClassifier, MINING_LABELS


class TestAudioFeatureExtractor:
    """测试音频特征提取器类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.extractor = AudioFeatureExtractor()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.extractor.sample_rate == 22050
        assert self.extractor.n_mfcc == 13
        assert self.extractor.n_fft == 2048
        assert self.extractor.hop_length == 512
    
    @patch('librosa.load')
    @patch('librosa.feature.mfcc')
    @patch('librosa.feature.zero_crossing_rate')
    @patch('librosa.feature.rms')
    @patch('librosa.feature.spectral_centroid')
    @patch('librosa.feature.spectral_rolloff')
    @patch('librosa.feature.spectral_bandwidth')
    def test_extract_features(self, mock_bandwidth, mock_rolloff, mock_centroid, 
                             mock_rms, mock_zcr, mock_mfcc, mock_load):
        """测试特征提取"""
        # 模拟音频数据
        mock_audio = np.random.random(22050)
        mock_sr = 22050
        
        # 模拟librosa函数返回值
        mock_load.return_value = (mock_audio, mock_sr)
        mock_mfcc.return_value = np.random.random((13, 43))
        mock_zcr.return_value = np.random.random((1, 43))
        mock_rms.return_value = np.random.random((1, 43))
        mock_centroid.return_value = np.random.random((1, 43))
        mock_rolloff.return_value = np.random.random((1, 43))
        mock_bandwidth.return_value = np.random.random((1, 43))
        
        # 创建临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b'fake_audio_data')
            temp_file.flush()
            
            try:
                features = self.extractor.extract_features(temp_file.name)
                
                # 验证特征提取结果
                assert features is not None
                assert features.shape == (68,)  # 18个特征 * 4个统计量
                assert not np.any(np.isnan(features))
                
            finally:
                os.unlink(temp_file.name)
    
    def test_extract_features_invalid_file(self):
        """测试无效文件的特征提取"""
        features = self.extractor.extract_features('nonexistent_file.wav')
        assert features is None


class TestMiningAudioClassifier:
    """测试矿业音频分类模型类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.model = MiningAudioClassifier(input_dim=68)
    
    def test_initialization(self):
        """测试初始化"""
        assert hasattr(self.model, 'feature_extractor')
        assert hasattr(self.model, 'equipment_status_head')
        assert hasattr(self.model, 'fault_type_head')
        assert hasattr(self.model, 'priority_head')
        
        # 检查输出维度
        assert self.model.equipment_status_head.out_features == len(MINING_LABELS['equipment_status'])
        assert self.model.fault_type_head.out_features == len(MINING_LABELS['fault_type'])
        assert self.model.priority_head.out_features == len(MINING_LABELS['priority'])
    
    def test_forward_pass(self):
        """测试前向传播"""
        # 创建测试输入
        batch_size = 4
        input_features = torch.randn(batch_size, 68)
        
        # 前向传播
        outputs = self.model(input_features)
        
        # 验证输出结构
        assert 'equipment_status' in outputs
        assert 'fault_type' in outputs
        assert 'priority' in outputs
        
        # 验证输出形状
        assert outputs['equipment_status'].shape == (batch_size, len(MINING_LABELS['equipment_status']))
        assert outputs['fault_type'].shape == (batch_size, len(MINING_LABELS['fault_type']))
        assert outputs['priority'].shape == (batch_size, len(MINING_LABELS['priority']))
        
        # 验证输出值范围（sigmoid激活函数）
        for output_name, output_tensor in outputs.items():
            assert torch.all(output_tensor >= 0) and torch.all(output_tensor <= 1)


class TestMiningAudioMLBackend:
    """测试矿业声音ML Backend类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with patch('torch.device'):
            with patch('torch.load'):
                with patch('os.path.exists', return_value=False):
                    self.backend = MiningAudioMLBackend()
                    self.backend.setup()
    
    def test_model_initialization(self):
        """测试模型初始化"""
        assert self.backend.get("model_version") == "mining_audio_v1.0"
        assert hasattr(self.backend, 'feature_extractor')
        assert hasattr(self.backend, 'model')
        assert hasattr(self.backend, 'scaler')
        assert self.backend.get('training_count') == 0
    
    def test_get_model_info(self):
        """测试获取模型信息"""
        info = self.backend.get_model_info()
        
        assert 'model_version' in info
        assert 'training_count' in info
        assert 'last_training_time' in info
        assert 'mining_labels' in info
        assert 'device' in info
        assert 'model_loaded' in info
        assert 'scaler_loaded' in info
        
        # 验证标签信息
        assert info['mining_labels'] == MINING_LABELS
    
    def test_health_check(self):
        """测试健康检查"""
        health = self.backend.health_check()
        
        assert 'status' in health
        assert health['status'] == 'healthy'
        assert 'model_version' in health
        assert 'model_loaded' in health
        assert 'scaler_loaded' in health
    
    def test_reset_model(self):
        """测试模型重置"""
        # 修改一些参数
        self.backend.set('training_count', 100)
        
        # 重置模型
        self.backend.reset_model()
        
        # 检查是否重置
        assert self.backend.get('training_count') == 0
        assert self.backend.get('model_version') == 'mining_audio_v1.0'
    
    def test_update_model_config(self):
        """测试模型配置更新"""
        config = {
            'model_version': 'mining_audio_v2.0',
            'prediction_threshold': 0.7
        }
        
        self.backend.update_model_config(config)
        
        # 验证配置更新
        assert self.backend.get('model_version') == 'mining_audio_v2.0'
    
    @patch.object(MiningAudioMLBackend, 'get_local_path')
    @patch.object(MiningAudioMLBackend, '_preprocess_audio')
    @patch.object(MiningAudioMLBackend, '_predict_labels')
    def test_predict_method(self, mock_predict, mock_preprocess, mock_get_path):
        """测试预测方法"""
        # 模拟数据
        mock_get_path.return_value = '/tmp/test_audio.wav'
        mock_preprocess.return_value = torch.randn(1, 68)
        mock_predict.return_value = {
            'equipment_status': [{'label': 'normal', 'confidence': 0.8}],
            'fault_type': [{'label': 'bearing_fault', 'confidence': 0.6}]
        }
        
        # 创建测试任务
        tasks = [{
            'id': 1,
            'data': {'audio': 'test_audio.wav'}
        }]
        
        # 执行预测
        response = self.backend.predict(tasks)
        
        # 验证响应
        assert hasattr(response, 'predictions')
        assert len(response.predictions) == 1
        
        # 验证预测结果
        prediction = response.predictions[0]
        assert 'result' in prediction
        assert 'model_version' in prediction
        assert 'task' in prediction
    
    def test_fit_method(self):
        """测试训练方法"""
        # 测试START_TRAINING事件
        event = 'START_TRAINING'
        data = {'training_data': 'test'}
        
        # 执行训练
        self.backend.fit(event, data)
        
        # 验证训练计数增加
        assert self.backend.get('training_count') == 1
        
        # 验证模型版本更新
        model_version = self.backend.get('model_version')
        assert 'mining_audio_v1.0_' in model_version


class TestMiningLabels:
    """测试矿业标签定义"""
    
    def test_mining_labels_structure(self):
        """测试矿业标签结构"""
        assert 'equipment_status' in MINING_LABELS
        assert 'fault_type' in MINING_LABELS
        assert 'priority' in MINING_LABELS
        
        # 验证设备状态标签
        equipment_labels = MINING_LABELS['equipment_status']
        assert 'normal' in equipment_labels
        assert 'abnormal' in equipment_labels
        assert 'maintenance_needed' in equipment_labels
        
        # 验证故障类型标签
        fault_labels = MINING_LABELS['fault_type']
        assert 'bearing_fault' in fault_labels
        assert 'motor_fault' in fault_labels
        assert 'hydraulic_leak' in fault_labels
        assert 'belt_fault' in fault_labels
        
        # 验证优先级标签
        priority_labels = MINING_LABELS['priority']
        assert 'low_priority' in priority_labels
        assert 'medium_priority' in priority_labels
        assert 'high_priority' in priority_labels


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
