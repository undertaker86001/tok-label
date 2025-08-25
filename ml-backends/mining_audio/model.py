"""
矿业声音样本ML Backend核心模型

基于Label Studio ML Backend架构，实现矿业音频的多标签分类服务
"""

from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
import librosa
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
import os
import pickle
import logging
import time

logger = logging.getLogger(__name__)

# 矿业场景标签定义
MINING_LABELS = {
    'equipment_status': ['normal', 'abnormal', 'maintenance_needed'],
    'fault_type': ['bearing_fault', 'motor_fault', 'hydraulic_leak', 'belt_fault'],
    'priority': ['low_priority', 'medium_priority', 'high_priority']
}


class AudioFeatureExtractor:
    """音频特征提取器"""
    
    def __init__(self, sample_rate=22050, n_mfcc=13, n_fft=2048, hop_length=512):
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        
    def extract_features(self, audio_path):
        """提取音频特征"""
        try:
            # 加载音频文件
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            # 时域特征
            zcr = librosa.feature.zero_crossing_rate(y, hop_length=self.hop_length)
            energy = librosa.feature.rms(y=y, hop_length=self.hop_length)
            
            # 频域特征
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=self.n_mfcc, 
                                       n_fft=self.n_fft, hop_length=self.hop_length)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, 
                                                                hop_length=self.hop_length)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, 
                                                              hop_length=self.hop_length)
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, 
                                                                   hop_length=self.hop_length)
            
            # 合并特征
            features = np.vstack([
                mfccs,
                zcr,
                energy,
                spectral_centroid,
                spectral_rolloff,
                spectral_bandwidth
            ])
            
            # 统计特征（均值、标准差、最大值、最小值）
            feature_stats = np.hstack([
                np.mean(features, axis=1),
                np.std(features, axis=1),
                np.max(features, axis=1),
                np.min(features, axis=1)
            ])
            
            return feature_stats
            
        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return None


class MiningAudioClassifier(nn.Module):
    """矿业音频多标签分类模型"""
    
    def __init__(self, input_dim, hidden_dims=[256, 128, 64]):
        super(MiningAudioClassifier, self).__init__()
        
        # 特征提取层
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_dim = hidden_dim
            
        self.feature_extractor = nn.Sequential(*layers)
        
        # 多标签分类头
        self.equipment_status_head = nn.Linear(prev_dim, len(MINING_LABELS['equipment_status']))
        self.fault_type_head = nn.Linear(prev_dim, len(MINING_LABELS['fault_type']))
        self.priority_head = nn.Linear(prev_dim, len(MINING_LABELS['priority']))
        
    def forward(self, x):
        features = self.feature_extractor(x)
        
        equipment_status = torch.sigmoid(self.equipment_status_head(features))
        fault_type = torch.sigmoid(self.fault_type_head(features))
        priority = torch.sigmoid(self.priority_head(features))
        
        return {
            'equipment_status': equipment_status,
            'fault_type': fault_type,
            'priority': priority
        }


class MiningAudioMLBackend(LabelStudioMLBase):
    """矿业声音样本ML Backend"""
    
    def setup(self):
        """初始化模型配置"""
        self.set("model_version", "mining_audio_v1.0")
        
        # 初始化特征提取器
        self.feature_extractor = AudioFeatureExtractor()
        
        # 模型路径
        self.model_path = os.getenv("MODEL_PATH", os.path.join(
            os.path.dirname(__file__), "mining_audio_model.pth"))
        self.scaler_path = os.getenv("SCALER_PATH", os.path.join(
            os.path.dirname(__file__), "feature_scaler.pkl"))
        
        # 加载模型和标准化器
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.scaler = None
        
        # 记录模型统计信息
        self.set('training_count', 0)
        self.set('last_training_time', time.time())
        
        self._load_model()
        logger.info("矿业声音ML Backend初始化完成")
        
    def _load_model(self):
        """加载预训练模型"""
        try:
            if os.path.exists(self.model_path):
                # 假设特征维度为68 (13 MFCC + 5 其他特征) * 4 统计量
                input_dim = 68
                self.model = MiningAudioClassifier(input_dim)
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                logger.info("模型加载成功")
            else:
                logger.warning("模型文件不存在，使用随机初始化模型")
                self.model = MiningAudioClassifier(68)
                self.model.to(self.device)
                
            # 加载特征标准化器
            if os.path.exists(self.scaler_path):
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("特征标准化器加载成功")
            else:
                self.scaler = StandardScaler()
                logger.warning("标准化器文件不存在，使用默认标准化器")
                
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            
    def _preprocess_audio(self, audio_path):
        """音频预处理"""
        features = self.feature_extractor.extract_features(audio_path)
        if features is None:
            return None
            
        # 特征标准化
        if self.scaler:
            features = self.scaler.transform(features.reshape(1, -1))
        else:
            features = features.reshape(1, -1)
            
        return torch.FloatTensor(features).to(self.device)
    
    def _predict_labels(self, features):
        """多标签预测"""
        with torch.no_grad():
            outputs = self.model(features)
            
        predictions = {}
        threshold = 0.5
        
        for category, logits in outputs.items():
            probs = logits.cpu().numpy()[0]
            predicted_labels = []
            
            for i, prob in enumerate(probs):
                if prob > threshold:
                    label_name = MINING_LABELS[category][i]
                    predicted_labels.append({
                        'label': label_name,
                        'confidence': float(prob)
                    })
                    
            predictions[category] = predicted_labels
            
        return predictions
    
    def _convert_to_labelstudio_format(self, predictions, task_id):
        """转换为Label Studio格式"""
        results = []
        
        for category, labels in predictions.items():
            if labels:  # 只添加有预测结果的类别
                for label_info in labels:
                    results.append({
                        "from_name": f"mining_{category}",
                        "to_name": "audio",
                        "type": "choices",
                        "value": {
                            "choices": [label_info['label']]
                        },
                        "score": label_info['confidence']
                    })
        
        return {
            "result": results,
            "model_version": self.get("model_version"),
            "task": task_id
        }
    
    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        """预测接口实现"""
        logger.info(f'运行矿业音频预测，任务数量: {len(tasks)}')
        predictions = []
        
        for task in tasks:
            try:
                # 获取音频文件路径
                audio_url = task['data'].get('audio')
                if not audio_url:
                    logger.warning(f"任务 {task.get('id')} 缺少音频数据")
                    continue
                
                # 下载音频文件到本地
                audio_path = self.get_local_path(audio_url, task_id=task.get('id'))
                
                # 特征提取
                features = self._preprocess_audio(audio_path)
                if features is None:
                    logger.error(f"音频特征提取失败: {audio_path}")
                    continue
                
                # 多标签预测
                label_predictions = self._predict_labels(features)
                
                # 转换为Label Studio格式
                ls_prediction = self._convert_to_labelstudio_format(
                    label_predictions, task.get('id'))
                
                predictions.append(ls_prediction)
                logger.info(f'任务 {task.get("id")} 预测成功，生成 {len(ls_prediction["result"])} 个预测结果')
                
            except Exception as e:
                logger.error(f"预测失败: {e}")
                continue
        
        logger.info(f"矿业音频预测完成，总共生成 {len(predictions)} 个预测结果")
        return ModelResponse(predictions=predictions)
    
    def fit(self, event, data, **kwargs):
        """模型训练接口"""
        logger.info(f'收到矿业音频训练事件: {event}')
        
        try:
            # 获取之前的模型参数
            old_model_version = self.get('model_version', 'mining_audio_v1.0')
            
            logger.info(f'当前模型版本: {old_model_version}')
            
            if event == 'START_TRAINING':
                # 这里可以实现模型训练逻辑
                # 从标注数据中提取特征和标签
                # 训练模型并保存
                logger.info("开始模型训练...")
                
                # 模拟训练过程
                time.sleep(1)
                
                # 更新模型版本
                new_version = f"mining_audio_v1.0_{int(time.time())}"
                self.set('model_version', new_version)
                logger.info(f'模型版本更新为: {new_version}')
            
            # 记录训练统计信息
            training_count = self.get('training_count', 0) + 1
            self.set('training_count', training_count)
            self.set('last_training_time', time.time())
            
            logger.info(f'矿业音频模型训练完成，总训练次数: {training_count}')
            
        except Exception as e:
            logger.error(f'矿业音频模型训练过程中出错: {e}')
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            'model_version': self.get('model_version', 'mining_audio_v1.0'),
            'training_count': self.get('training_count', 0),
            'last_training_time': self.get('last_training_time', 0),
            'mining_labels': MINING_LABELS,
            'device': str(self.device),
            'model_loaded': self.model is not None,
            'scaler_loaded': self.scaler is not None
        }
    
    def reset_model(self):
        """重置模型参数到默认值"""
        try:
            # 重置模型版本
            self.set('model_version', 'mining_audio_v1.0')
            self.set('training_count', 0)
            self.set('last_training_time', time.time())
            
            # 重新加载模型
            self._load_model()
            
            logger.info("模型参数已重置到默认值")
            
        except Exception as e:
            logger.error(f"重置模型参数失败: {e}")
    
    def update_model_config(self, config: Dict):
        """更新模型配置"""
        try:
            if 'model_version' in config:
                self.set('model_version', config['model_version'])
                logger.info(f"模型版本已更新: {config['model_version']}")
            
            if 'prediction_threshold' in config:
                # 可以更新预测阈值
                logger.info(f"预测阈值已更新: {config['prediction_threshold']}")
            
        except Exception as e:
            logger.error(f"更新模型配置失败: {e}")
    
    def health_check(self) -> Dict:
        """健康检查"""
        try:
            return {
                'status': 'healthy',
                'model_version': self.get('model_version', 'unknown'),
                'model_loaded': self.model is not None,
                'scaler_loaded': self.scaler is not None,
                'device': str(self.device),
                'last_training': self.get('last_training_time', 0),
                'training_count': self.get('training_count', 0)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
