"""
声音ML Backend的端到端测试

测试完整的声音ML Backend服务流程，包括：
- 服务启动和健康检查
- 音频数据加载和预处理
- 语音识别和音频分类
- API接口响应
- 模型训练和参数更新
- 错误处理和性能测试
"""

import pytest
import requests
import time
import json
import numpy as np
import tempfile
import os
import subprocess
import signal
from unittest.mock import patch, MagicMock
import logging
import wave
import io
import base64

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


class TestAudioBackendE2E:
    """声音ML Backend端到端测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化，启动ML Backend服务"""
        cls.service_process = None
        cls.service_url = f"{TEST_CONFIG['base_url']}"
        
        # 检查服务是否已经在运行
        if cls._is_service_running():
            logger.info("声音ML Backend服务已在运行")
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
        """启动声音ML Backend服务"""
        try:
            logger.info("启动声音ML Backend服务...")
            
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
        """停止声音ML Backend服务"""
        if cls.service_process:
            logger.info("停止声音ML Backend服务...")
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
    
    def _create_test_audio_data(self, duration=3.0, sample_rate=16000):
        """创建测试音频数据"""
        # 生成正弦波作为测试音频
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # 440 Hz正弦波
        audio_data = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # 添加一些噪声
        audio_data += 0.01 * np.random.randn(len(audio_data))
        
        return audio_data, sample_rate
    
    def _create_test_wav_file(self, duration=3.0, sample_rate=16000):
        """创建测试WAV文件"""
        audio_data, sr = self._create_test_audio_data(duration, sample_rate)
        
        # 创建临时WAV文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            with wave.open(temp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sr)
                wav_file.writeframes((audio_data * 32767).astype(np.int16).tobytes())
            
            return temp_file.name
    
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
        assert 'annotation_types' in model_info
        
        # 验证支持的标注类型
        annotation_types = model_info['annotation_types']
        assert 'speech_recognition' in annotation_types
        assert 'audio_classification' in annotation_types
        
        logger.info(f"模型信息: {model_info}")
    
    def test_03_speech_recognition_prediction(self):
        """测试语音识别预测功能"""
        logger.info("测试语音识别预测功能...")
        
        # 创建测试音频文件
        test_wav_path = self._create_test_wav_file(duration=3.0)
        
        try:
            # 准备预测请求
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_wav_path,
                            "audio_type": "speech"
                        }
                    }
                ]
            }
            
            # 模拟音频处理
            with patch('audio_utils.AudioProcessor.load_audio') as mock_load:
                with patch('audio_predictor.AudioPredictor.transcribe_audio') as mock_transcribe:
                    # 模拟转录结果
                    mock_transcribe.return_value = [
                        {"start": 0.0, "end": 1.5, "text": "测试语音识别"},
                        {"start": 1.5, "end": 3.0, "text": "继续测试"}
                    ]
                    
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
                        
                        # 验证转录结果
                        results = first_prediction['result']
                        transcription_results = [r for r in results if r['from_name'] == 'transcription']
                        
                        assert len(transcription_results) > 0
                        for result in transcription_results:
                            assert result['type'] == 'textarea'
                            assert 'text' in result['value']
                        
                        logger.info(f"语音识别预测成功，生成了 {len(predictions)} 个预测结果")
                    else:
                        logger.info("语音识别预测完成，但未生成预测结果")
        
        finally:
            # 清理临时文件
            if os.path.exists(test_wav_path):
                os.unlink(test_wav_path)
    
    def test_04_audio_classification_prediction(self):
        """测试音频分类预测功能"""
        logger.info("测试音频分类预测功能...")
        
        # 创建测试音频文件
        test_wav_path = self._create_test_wav_file(duration=2.0)
        
        try:
            # 准备预测请求
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_wav_path,
                            "audio_type": "classification"
                        }
                    }
                ]
            }
            
            # 模拟音频分类
            with patch('audio_utils.AudioProcessor.load_audio') as mock_load:
                with patch('audio_predictor.AudioPredictor.classify_audio') as mock_classify:
                    # 模拟分类结果
                    mock_classify.return_value = {
                        "label": "语音",
                        "confidence": 0.85
                    }
                    
                    response = self._make_request('POST', '/predict', data=prediction_request)
                    
                    assert response.status_code == 200
                    prediction_result = response.json()
                    
                    # 验证预测结果
                    assert 'predictions' in prediction_result
                    predictions = prediction_result['predictions']
                    
                    if len(predictions) > 0:
                        # 验证分类结果
                        results = first_prediction['result']
                        classification_results = [r for r in results if r['from_name'] == 'audio_type']
                        
                        assert len(classification_results) > 0
                        for result in classification_results:
                            assert result['type'] == 'choices'
                            assert 'choices' in result['value']
                        
                        logger.info(f"音频分类预测成功，生成了 {len(predictions)} 个预测结果")
                    else:
                        logger.info("音频分类预测完成，但未生成预测结果")
        
        finally:
            # 清理临时文件
            if os.path.exists(test_wav_path):
                os.unlink(test_wav_path)
    
    def test_05_mixed_annotation_prediction(self):
        """测试混合标注预测功能（语音识别+分类）"""
        logger.info("测试混合标注预测功能...")
        
        # 创建测试音频文件
        test_wav_path = self._create_test_wav_file(duration=4.0)
        
        try:
            # 准备预测请求
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_wav_path,
                            "audio_type": "mixed"
                        }
                    }
                ]
            }
            
            # 模拟音频处理
            with patch('audio_utils.AudioProcessor.load_audio') as mock_load:
                with patch('audio_predictor.AudioPredictor.transcribe_audio') as mock_transcribe:
                    with patch('audio_predictor.AudioPredictor.classify_audio') as mock_classify:
                        # 模拟转录结果
                        mock_transcribe.return_value = [
                            {"start": 0.0, "end": 2.0, "text": "混合标注测试"},
                            {"start": 2.0, "end": 4.0, "text": "语音识别和分类"}
                        ]
                        
                        # 模拟分类结果
                        mock_classify.return_value = {
                            "label": "语音",
                            "confidence": 0.92
                        }
                        
                        response = self._make_request('POST', '/predict', data=prediction_request)
                        
                        assert response.status_code == 200
                        prediction_result = response.json()
                        
                        # 验证预测结果
                        assert 'predictions' in prediction_result
                        predictions = prediction_result['predictions']
                        
                        if len(predictions) > 0:
                            # 验证包含两种类型的标注
                            results = first_prediction['result']
                            transcription_count = len([r for r in results if r['from_name'] == 'transcription'])
                            classification_count = len([r for r in results if r['from_name'] == 'audio_type'])
                            
                            assert transcription_count > 0, "应该包含语音识别结果"
                            assert classification_count > 0, "应该包含音频分类结果"
                            
                            logger.info(f"混合标注预测成功，转录: {transcription_count}，分类: {classification_count}")
                        else:
                            logger.info("混合标注预测完成，但未生成预测结果")
        
        finally:
            # 清理临时文件
            if os.path.exists(test_wav_path):
                os.unlink(test_wav_path)
    
    def test_06_model_training(self):
        """测试模型训练功能"""
        logger.info("测试模型训练功能...")
        
        # 准备训练数据（模拟人工标注）
        training_data = {
            "event": "ANNOTATION_CREATED",
            "annotation": {
                "id": 1,
                "result": [
                    {
                        "from_name": "transcription",
                        "type": "textarea",
                        "value": {
                            "text": ["测试语音识别训练"]
                        }
                    },
                    {
                        "from_name": "audio_type",
                        "type": "choices",
                        "value": {
                            "choices": ["语音"]
                        }
                    }
                ]
            },
            "task": {
                "id": 1,
                "data": {
                    "audio": "test_audio.wav"
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
    
    def test_07_error_handling(self):
        """测试错误处理"""
        logger.info("测试错误处理...")
        
        # 测试无效的预测请求
        invalid_request = {
            "tasks": [
                {
                    "data": {
                        "audio": "nonexistent.wav",
                        "audio_type": "invalid_type"
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
        
        # 测试无效的音频格式
        invalid_audio_request = {
            "tasks": [
                {
                    "data": {
                        "audio": "test.txt",  # 无效的音频格式
                        "audio_type": "speech"
                    }
                }
            ]
        }
        
        response = self._make_request('POST', '/predict', data=invalid_audio_request)
        assert response.status_code == 200
        
        logger.info("错误处理测试完成")
    
    def test_08_performance_test(self):
        """测试性能"""
        logger.info("测试性能...")
        
        # 创建较长的测试音频文件
        test_wav_path = self._create_test_wav_file(duration=10.0)
        
        try:
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_wav_path,
                            "audio_type": "mixed"
                        }
                    }
                ]
            }
            
            with patch('audio_utils.AudioProcessor.load_audio') as mock_load:
                with patch('audio_predictor.AudioPredictor.transcribe_audio') as mock_transcribe:
                    with patch('audio_predictor.AudioPredictor.classify_audio') as mock_classify:
                        # 模拟处理结果
                        mock_transcribe.return_value = [
                            {"start": i, "end": i+1, "text": f"第{i}秒"} 
                            for i in range(10)
                        ]
                        mock_classify.return_value = {"label": "语音", "confidence": 0.9}
                        
                        start_time = time.time()
                        response = self._make_request('POST', '/predict', data=prediction_request)
                        end_time = time.time()
                        
                        processing_time = end_time - start_time
                        
                        assert response.status_code == 200
                        assert processing_time < 15.0, f"预测处理时间过长: {processing_time:.2f}秒"
                        
                        logger.info(f"性能测试完成，处理时间: {processing_time:.2f}秒")
        
        finally:
            # 清理临时文件
            if os.path.exists(test_wav_path):
                os.unlink(test_wav_path)
    
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
        assert final_info['model_version'] == 'audio_annotation_v1.0'
        
        logger.info("模型重置测试完成")
    
    def test_10_audio_format_support(self):
        """测试音频格式支持"""
        logger.info("测试音频格式支持...")
        
        # 测试不同格式的音频文件
        test_formats = [
            (3.0, 16000, '.wav'),
            (2.0, 22050, '.wav'),
            (1.5, 44100, '.wav')
        ]
        
        for duration, sample_rate, format_ext in test_formats:
            test_audio_path = self._create_test_wav_file(duration, sample_rate)
            
            try:
                prediction_request = {
                    "tasks": [
                        {
                            "data": {
                                "audio": test_audio_path,
                                "audio_type": "speech"
                            }
                        }
                    ]
                }
                
                with patch('audio_utils.AudioProcessor.load_audio') as mock_load:
                    with patch('audio_predictor.AudioPredictor.transcribe_audio') as mock_transcribe:
                        mock_transcribe.return_value = [
                            {"start": 0.0, "end": duration, "text": f"测试{duration}秒音频"}
                        ]
                        
                        response = self._make_request('POST', '/predict', data=prediction_request)
                        assert response.status_code == 200
                        
                        logger.info(f"格式 {format_ext} ({sample_rate}Hz) 支持测试通过")
            
            finally:
                if os.path.exists(test_audio_path):
                    os.unlink(test_audio_path)


class TestAudioBackendIntegration:
    """声音ML Backend集成测试类"""
    
    def test_model_initialization(self):
        """测试模型初始化"""
        from model import AudioAnnotationModel
        
        model = AudioAnnotationModel()
        model.setup()
        
        assert model.get("model_version") == "audio_annotation_v1.0"
        assert hasattr(model, 'audio_processor')
        assert hasattr(model, 'audio_predictor')
        assert "speech_recognition" in model.annotation_types
    
    def test_audio_processor_functionality(self):
        """测试音频处理器功能"""
        from audio_utils import AudioProcessor
        
        processor = AudioProcessor()
        
        # 测试音频标准化
        test_audio = np.array([0.5, -0.8, 0.3, -0.2])
        normalized = processor._normalize_audio(test_audio)
        
        assert np.max(np.abs(normalized)) <= 1.0
        assert len(normalized) == len(test_audio)
    
    def test_audio_predictor_functionality(self):
        """测试音频预测器功能"""
        from audio_predictor import AudioPredictor
        
        with patch('whisper.load_model'):
            with patch('transformers.pipeline'):
                predictor = AudioPredictor()
                
                # 测试音频分类
                test_audio = np.random.random(16000)
                result = predictor.classify_audio(test_audio)
                
                assert result is not None
                assert "label" in result
                assert "confidence" in result
    
    def test_prediction_formatting(self):
        """测试预测结果格式化"""
        from model import AudioAnnotationModel
        
        model = AudioAnnotationModel()
        
        # 测试转录结果格式化
        transcription_data = [
            {"start": 0.0, "end": 2.0, "text": "测试语音"},
            {"start": 2.0, "end": 4.0, "text": "继续测试"}
        ]
        
        results = model._format_transcription_results(transcription_data)
        assert len(results) == 2
        assert all(r["type"] == "textarea" for r in results)
        
        # 测试分类结果格式化
        classification_data = {"label": "语音", "confidence": 0.8}
        results = model._format_classification_results(classification_data)
        assert len(results) == 1
        assert results[0]["type"] == "choices"


if __name__ == "__main__":
    # 运行端到端测试
    pytest.main([__file__, "-v", "--tb=short"])
