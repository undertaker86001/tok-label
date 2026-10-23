"""
矿业声音ML Backend的API测试脚本

测试各个API接口的功能和性能，包括：
- 健康检查接口
- 模型信息接口
- 预测接口
- 训练接口
- 模型重置接口
"""

import requests
import json
import os
import time
import argparse
import logging
import numpy as np
import tempfile
import wave
from pathlib import Path
import sys

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class MiningAudioAPITester:
    """矿业声音ML Backend API测试器"""
    
    def __init__(self, base_url, timeout=30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        # 测试结果统计
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'total': 0
        }
    
    def _make_request(self, method, endpoint, data=None, headers=None, expected_status=None):
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            # 检查状态码
            if expected_status and response.status_code != expected_status:
                logger.warning(f"期望状态码 {expected_status}，实际状态码 {response.status_code}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            return None
    
    def _create_test_audio_file(self, duration=3.0, sample_rate=22050, filename="test_audio.wav"):
        """创建测试音频文件"""
        try:
            # 生成正弦波作为测试音频
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_data = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz正弦波
            
            # 添加噪声
            audio_data += 0.01 * np.random.randn(len(audio_data))
            
            # 创建临时WAV文件
            temp_dir = Path("temp_audio")
            temp_dir.mkdir(exist_ok=True)
            
            audio_path = temp_dir / filename
            
            with wave.open(str(audio_path), 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sample_rate)
                wav_file.writeframes((audio_data * 32767).astype(np.int16).tobytes())
            
            return str(audio_path)
            
        except Exception as e:
            logger.error(f"创建测试音频文件失败: {e}")
            return None
    
    def _cleanup_test_files(self):
        """清理测试文件"""
        try:
            temp_dir = Path("temp_audio")
            if temp_dir.exists():
                for file_path in temp_dir.glob("*.wav"):
                    file_path.unlink()
                temp_dir.rmdir()
                logger.info("测试文件清理完成")
        except Exception as e:
            logger.warning(f"清理测试文件失败: {e}")
    
    def test_health_check(self):
        """测试健康检查接口"""
        logger.info("测试健康检查接口...")
        
        response = self._make_request('GET', '/health', expected_status=200)
        if not response:
            return self._record_test_result(False, "健康检查请求失败")
        
        try:
            health_data = response.json()
            
            # 验证响应结构
            required_fields = ['status', 'model_version', 'model_loaded', 'scaler_loaded']
            for field in required_fields:
                if field not in health_data:
                    return self._record_test_result(False, f"健康检查响应缺少字段: {field}")
            
            # 验证状态
            if health_data['status'] != 'healthy':
                return self._record_test_result(False, f"服务状态异常: {health_data['status']}")
            
            logger.info(f"健康检查通过: {health_data}")
            return self._record_test_result(True, "健康检查测试通过")
            
        except json.JSONDecodeError as e:
            return self._record_test_result(False, f"健康检查响应JSON解析失败: {e}")
    
    def test_model_info(self):
        """测试模型信息接口"""
        logger.info("测试模型信息接口...")
        
        response = self._make_request('GET', '/model/info', expected_status=200)
        if not response:
            return self._record_test_result(False, "模型信息请求失败")
        
        try:
            model_info = response.json()
            
            # 验证响应结构
            required_fields = ['model_version', 'training_count', 'last_training_time', 'mining_labels']
            for field in required_fields:
                if field not in model_info:
                    return self._record_test_result(False, f"模型信息响应缺少字段: {field}")
            
            # 验证矿业标签
            mining_labels = model_info['mining_labels']
            expected_categories = ['equipment_status', 'fault_type', 'priority']
            for category in expected_categories:
                if category not in mining_labels:
                    return self._record_test_result(False, f"模型信息缺少类别: {category}")
            
            logger.info(f"模型信息测试通过: {model_info}")
            return self._record_test_result(True, "模型信息测试通过")
            
        except json.JSONDecodeError as e:
            return self._record_test_result(False, f"模型信息响应JSON解析失败: {e}")
    
    def test_prediction_api(self):
        """测试预测接口"""
        logger.info("测试预测接口...")
        
        # 创建测试音频文件
        test_audio_path = self._create_test_audio_file(duration=3.0)
        if not test_audio_path:
            return self._record_test_result(False, "无法创建测试音频文件")
        
        try:
            # 准备预测请求
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_audio_path
                        }
                    }
                ]
            }
            
            # 发送预测请求
            response = self._make_request('POST', '/predict', data=prediction_request, expected_status=200)
            if not response:
                return self._record_test_result(False, "预测请求失败")
            
            try:
                prediction_result = response.json()
                
                # 验证响应结构
                if 'predictions' not in prediction_result:
                    return self._record_test_result(False, "预测响应缺少predictions字段")
                
                predictions = prediction_result['predictions']
                if len(predictions) > 0:
                    # 验证预测结果格式
                    first_prediction = predictions[0]
                    if 'result' not in first_prediction:
                        return self._record_test_result(False, "预测结果缺少result字段")
                    
                    results = first_prediction['result']
                    if len(results) > 0:
                        # 验证结果格式
                        for result in results:
                            required_fields = ['from_name', 'to_name', 'type', 'value']
                            for field in required_fields:
                                if field not in result:
                                    return self._record_test_result(False, f"预测结果缺少字段: {field}")
                        
                        logger.info(f"预测接口测试通过，生成了 {len(predictions)} 个预测结果")
                        return self._record_test_result(True, "预测接口测试通过")
                    else:
                        logger.info("预测完成，但未生成预测结果（可能是阈值设置过高）")
                        return self._record_test_result(True, "预测接口测试通过（无预测结果）")
                else:
                    logger.info("预测完成，但未生成预测结果")
                    return self._record_test_result(True, "预测接口测试通过（无预测结果）")
                
            except json.JSONDecodeError as e:
                return self._record_test_result(False, f"预测响应JSON解析失败: {e}")
                
        finally:
            # 清理测试文件
            if os.path.exists(test_audio_path):
                os.unlink(test_audio_path)
    
    def test_training_api(self):
        """测试训练接口"""
        logger.info("测试训练接口...")
        
        # 准备训练数据
        training_data = {
            "event": "START_TRAINING",
            "annotation": {
                "id": 1,
                "result": [
                    {
                        "from_name": "mining_equipment_status",
                        "type": "choices",
                        "value": {
                            "choices": ["normal"]
                        }
                    },
                    {
                        "from_name": "mining_fault_type",
                        "type": "choices",
                        "value": {
                            "choices": ["bearing_fault"]
                        }
                    }
                ]
            },
            "task": {
                "id": 1,
                "data": {
                    "audio": "test_mining_audio.wav"
                }
            }
        }
        
        # 发送训练请求
        response = self._make_request('POST', '/fit', data=training_data, expected_status=[200, 204])
        if not response:
            return self._record_test_result(False, "训练请求失败")
        
        logger.info(f"训练接口测试通过，状态码: {response.status_code}")
        return self._record_test_result(True, "训练接口测试通过")
    
    def test_model_reset(self):
        """测试模型重置接口"""
        logger.info("测试模型重置接口...")
        
        # 获取重置前的模型信息
        initial_response = self._make_request('GET', '/model/info')
        if not initial_response:
            return self._record_test_result(False, "获取初始模型信息失败")
        
        try:
            initial_info = initial_response.json()
            initial_training_count = initial_info.get('training_count', 0)
            
            # 发送重置请求
            reset_response = self._make_request('POST', '/model/reset', expected_status=[200, 204])
            if not reset_response:
                return self._record_test_result(False, "模型重置请求失败")
            
            # 等待重置完成
            time.sleep(2)
            
            # 检查重置后的状态
            final_response = self._make_request('GET', '/model/info')
            if not final_response:
                return self._record_test_result(False, "获取重置后模型信息失败")
            
            final_info = final_response.json()
            final_training_count = final_info.get('training_count', 0)
            
            # 验证重置
            if final_training_count == 0:
                logger.info("模型重置测试通过")
                return self._record_test_result(True, "模型重置测试通过")
            else:
                return self._record_test_result(False, f"模型重置失败，训练计数: {final_training_count}")
                
        except json.JSONDecodeError as e:
            return self._record_test_result(False, f"模型信息响应JSON解析失败: {e}")
    
    def test_error_handling(self):
        """测试错误处理"""
        logger.info("测试错误处理...")
        
        # 测试无效的预测请求
        invalid_request = {
            "tasks": [
                {
                    "data": {
                        "audio": "nonexistent.wav"
                    }
                }
            ]
        }
        
        response = self._make_request('POST', '/predict', data=invalid_request, expected_status=200)
        if not response:
            return self._record_test_result(False, "无效预测请求失败")
        
        # 测试无效的训练数据
        invalid_training_data = {
            "event": "INVALID_EVENT",
            "data": "invalid_data"
        }
        
        response = self._make_request('POST', '/fit', data=invalid_training_data, expected_status=[200, 204, 400])
        if not response:
            return self._record_test_result(False, "无效训练数据请求失败")
        
        logger.info("错误处理测试通过")
        return self._record_test_result(True, "错误处理测试通过")
    
    def test_performance(self):
        """测试性能"""
        logger.info("测试性能...")
        
        # 创建较长的测试音频文件
        test_audio_path = self._create_test_audio_file(duration=10.0, filename="performance_test.wav")
        if not test_audio_path:
            return self._record_test_result(False, "无法创建性能测试音频文件")
        
        try:
            prediction_request = {
                "tasks": [
                    {
                        "data": {
                            "audio": test_audio_path
                        }
                    }
                ]
            }
            
            # 测试响应时间
            start_time = time.time()
            response = self._make_request('POST', '/predict', data=prediction_request, expected_status=200)
            end_time = time.time()
            
            if not response:
                return self._record_test_result(False, "性能测试请求失败")
            
            processing_time = end_time - start_time
            
            # 性能要求：10秒音频应该在15秒内处理完成
            if processing_time < 15.0:
                logger.info(f"性能测试通过，处理时间: {processing_time:.2f}秒")
                return self._record_test_result(True, f"性能测试通过，处理时间: {processing_time:.2f}秒")
            else:
                return self._record_test_result(False, f"性能测试失败，处理时间过长: {processing_time:.2f}秒")
                
        finally:
            # 清理测试文件
            if os.path.exists(test_audio_path):
                os.unlink(test_audio_path)
    
    def test_audio_format_support(self):
        """测试音频格式支持"""
        logger.info("测试音频格式支持...")
        
        # 测试不同格式的音频文件
        test_formats = [
            (3.0, 22050, "format_test_22k.wav"),
            (2.0, 16000, "format_test_16k.wav"),
            (1.5, 44100, "format_test_44k.wav")
        ]
        
        passed_tests = 0
        total_tests = len(test_formats)
        
        for duration, sample_rate, filename in test_formats:
            test_audio_path = self._create_test_audio_file(duration, sample_rate, filename)
            if not test_audio_path:
                continue
            
            try:
                prediction_request = {
                    "tasks": [
                        {
                            "data": {
                                "audio": test_audio_path
                            }
                        }
                    ]
                }
                
                response = self._make_request('POST', '/predict', data=prediction_request, expected_status=200)
                if response:
                    passed_tests += 1
                    logger.info(f"格式 {filename} ({sample_rate}Hz) 支持测试通过")
                else:
                    logger.warning(f"格式 {filename} ({sample_rate}Hz) 支持测试失败")
                
            finally:
                if os.path.exists(test_audio_path):
                    os.unlink(test_audio_path)
        
        success_rate = passed_tests / total_tests if total_tests > 0 else 0
        if success_rate >= 0.8:  # 80%以上的格式支持测试通过
            logger.info(f"音频格式支持测试通过，成功率: {success_rate:.2%}")
            return self._record_test_result(True, f"音频格式支持测试通过，成功率: {success_rate:.2%}")
        else:
            return self._record_test_result(False, f"音频格式支持测试失败，成功率: {success_rate:.2%}")
    
    def _record_test_result(self, passed, message):
        """记录测试结果"""
        self.test_results['total'] += 1
        if passed:
            self.test_results['passed'] += 1
            logger.info(f"✅ {message}")
        else:
            self.test_results['failed'] += 1
            logger.error(f"❌ {message}")
        
        return passed
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始运行矿业声音ML Backend API测试...")
        logger.info(f"测试目标: {self.base_url}")
        
        # 测试列表
        test_functions = [
            self.test_health_check,
            self.test_model_info,
            self.test_prediction_api,
            self.test_training_api,
            self.test_model_reset,
            self.test_error_handling,
            self.test_performance,
            self.test_audio_format_support
        ]
        
        # 运行测试
        for test_func in test_functions:
            try:
                test_func()
            except Exception as e:
                logger.error(f"测试 {test_func.__name__} 执行异常: {e}")
                self._record_test_result(False, f"测试执行异常: {e}")
        
        # 输出测试结果
        self._print_test_summary()
        
        # 清理测试文件
        self._cleanup_test_files()
        
        return self.test_results['failed'] == 0
    
    def _print_test_summary(self):
        """打印测试结果摘要"""
        logger.info("\n" + "="*50)
        logger.info("测试结果摘要")
        logger.info("="*50)
        logger.info(f"总测试数: {self.test_results['total']}")
        logger.info(f"通过: {self.test_results['passed']}")
        logger.info(f"失败: {self.test_results['failed']}")
        
        success_rate = (self.test_results['passed'] / self.test_results['total'] * 100) if self.test_results['total'] > 0 else 0
        logger.info(f"成功率: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            logger.info("🎉 所有测试通过！")
        else:
            logger.info(f"⚠️  有 {self.test_results['failed']} 个测试失败")
        
        logger.info("="*50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='测试矿业声音ML Backend API')
    parser.add_argument('--url', type=str, default='http://localhost:9091',
                       help='ML Backend服务URL')
    parser.add_argument('--timeout', type=int, default=30,
                       help='请求超时时间（秒）')
    parser.add_argument('--wait', type=int, default=5,
                       help='等待服务启动的时间（秒）')
    
    args = parser.parse_args()
    
    # 等待服务启动
    if args.wait > 0:
        logger.info(f"等待服务启动 {args.wait} 秒...")
        time.sleep(args.wait)
    
    # 创建测试器
    tester = MiningAudioAPITester(args.url, args.timeout)
    
    try:
        # 运行所有测试
        success = tester.run_all_tests()
        
        # 设置退出码
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
