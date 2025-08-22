"""
音频标注ML Backend的测试文件

测试各个组件的功能和集成
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# 导入被测试的模块
from model import AudioAnnotationModel
from audio_predictor import AudioPredictor
from audio_utils import AudioProcessor


class TestAudioProcessor:
    """测试音频处理器类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.processor = AudioProcessor()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.processor.sample_rate == 16000
        assert '.wav' in self.processor.supported_formats
        assert '.mp3' in self.processor.supported_formats
    
    def test_normalize_audio(self):
        """测试音频标准化"""
        # 创建测试音频数据
        audio_data = np.array([0.5, -0.8, 0.3, -0.2])
        normalized = self.processor._normalize_audio(audio_data)
        
        # 检查标准化结果
        assert np.max(np.abs(normalized)) <= 1.0
        assert np.abs(np.mean(normalized)) < 1e-10  # DC偏移应该被移除
    
    def test_get_current_timestamp(self):
        """测试时间戳获取"""
        timestamp = self.processor.get_current_timestamp()
        assert isinstance(timestamp, str)
        assert 'T' in timestamp  # ISO格式应该包含T


class TestAudioPredictor:
    """测试音频预测器类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with patch('whisper.load_model'):
            with patch('transformers.pipeline'):
                self.predictor = AudioPredictor()
    
    def test_initialization(self):
        """测试初始化"""
        assert hasattr(self.predictor, 'whisper_model')
        assert hasattr(self.predictor, 'audio_classifier')
        assert hasattr(self.predictor, 'device')
    
    def test_classify_audio(self):
        """测试音频分类"""
        # 创建测试音频数据
        audio_data = np.random.random(16000)
        
        # 测试分类
        result = self.predictor.classify_audio(audio_data)
        
        # 验证结果
        assert result is not None
        assert "label" in result
        assert "confidence" in result
        assert result["label"] in ["语音", "音乐", "噪音"]
        assert 0 <= result["confidence"] <= 1


class TestAudioAnnotationModel:
    """测试音频标注模型类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with patch('audio_predictor.AudioPredictor'):
            with patch('audio_utils.AudioProcessor'):
                self.model = AudioAnnotationModel()
                self.model.setup()
    
    def test_model_initialization(self):
        """测试模型初始化"""
        assert self.model.get("model_version") == "audio_annotation_v1.0"
        assert hasattr(self.model, 'audio_processor')
        assert hasattr(self.model, 'audio_predictor')
        assert "speech_recognition" in self.model.annotation_types
    
    def test_format_transcription_results(self):
        """测试转录结果格式化"""
        transcription_data = [
            {"start": 0.0, "end": 2.0, "text": "测试语音"},
            {"start": 2.0, "end": 4.0, "text": "继续测试"}
        ]
        
        results = self.model._format_transcription_results(transcription_data)
        
        assert len(results) == 2
        assert results[0]["from_name"] == "transcription"
        assert results[0]["to_name"] == "audio"
        assert results[0]["type"] == "textarea"
        assert results[0]["value"]["text"] == ["测试语音"]
    
    def test_format_classification_results(self):
        """测试分类结果格式化"""
        classification_data = {"label": "语音", "confidence": 0.8}
        
        results = self.model._format_classification_results(classification_data)
        
        assert len(results) == 1
        assert results[0]["from_name"] == "audio_type"
        assert results[0]["to_name"] == "audio"
        assert results[0]["type"] == "choices"
        assert results[0]["value"]["choices"] == ["语音"]


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
