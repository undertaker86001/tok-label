import numpy as np
import pandas as pd
from scipy import signal
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from toklabel.prediction import BasePredictor, TimeseriesSpan, Number
from typing import List, Dict, Optional

class VibrationPredictor(BasePredictor):
    """振动数据PHM预测器 - 实现多标签自动化标注"""
    
    def __init__(self):
        super().__init__()
        # 转速阈值配置
        self.speed_thresholds = {
            '低转速': (0, 800),
            '中转速': (800, 1500),   
            '高转速': (1500, 3000)
        }
        # 故障检测模型
        self.fault_model = IsolationForest(contamination=0.1, random_state=42)
        self.quality_model = None
        self.scaler = StandardScaler()
        
    def extract_features(self, data: pd.DataFrame) -> Dict:
        """提取振动特征 - 时域和频域特征"""
        features = {}
        
        # 时域特征提取
        for axis in ['vibration_x', 'vibration_y', 'vibration_z']:
            if axis in data.columns:
                vibration = data[axis]
                features[f'{axis}_rms'] = np.sqrt(np.mean(vibration**2))  # 均方根值
                features[f'{axis}_peak'] = np.max(np.abs(vibration))      # 峰值
                features[f'{axis}_std'] = np.std(vibration)               # 标准差
                features[f'{axis}_kurtosis'] = signal.kurtosis(vibration) # 峰度
                features[f'{axis}_skewness'] = signal.skew(vibration)     # 偏度
                features[f'{axis}_crest_factor'] = features[f'{axis}_peak'] / max(features[f'{axis}_rms'], 1e-6)  # 峰值因子
        
        # 频域特征提取
        if 'vibration_amplitude' in data.columns:
            amplitude = data['vibration_amplitude']
            freqs, psd = signal.welch(amplitude, fs=1000)  # 1kHz采样率
            features['dominant_freq'] = freqs[np.argmax(psd)]  # 主频
            features['spectral_centroid'] = np.sum(freqs * psd) / np.sum(psd)  # 频谱质心
            features['spectral_rolloff'] = self._calculate_spectral_rolloff(freqs, psd)  # 频谱滚降
            features['spectral_bandwidth'] = np.sqrt(np.sum(((freqs - features['spectral_centroid'])**2) * psd) / np.sum(psd))  # 频谱带宽
        
        # 转速特征
        if 'rotation_speed' in data.columns:
            rpm = data['rotation_speed']
            features['rpm_mean'] = np.mean(rpm)
            features['rpm_std'] = np.std(rpm)
            features['rpm_max'] = np.max(rpm)
            features['rpm_min'] = np.min(rpm)
            
        return features
    
    def _calculate_spectral_rolloff(self, freqs: np.ndarray, psd: np.ndarray, rolloff_percent: float = 0.85) -> float:
        """计算频谱滚降点"""
        cumsum_psd = np.cumsum(psd)
        total_energy = cumsum_psd[-1]
        rolloff_energy = total_energy * rolloff_percent
        rolloff_idx = np.where(cumsum_psd >= rolloff_energy)[0]
        return freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else freqs[-1]
    
    def predict_speed_segments(self, data: pd.DataFrame) -> List[TimeseriesSpan]:
        """预测转速段 - 创建多个TimeseriesSpan对象标注不同转速段"""
        predictions = []
        if 'rotation_speed' not in data.columns:
            return predictions
            
        rpm_data = data['rotation_speed']
        time = data['time'] if 'time' in data.columns else np.arange(len(rpm_data)) * 0.001
        
        # 使用滑动窗口检测转速段
        window_size = 1000  # 1秒窗口
        step_size = window_size // 2
        
        current_speed_label = None
        segment_start = None
        
        for i in range(0, len(rpm_data) - window_size, step_size):
            window_rpm = rpm_data[i:i+window_size]
            avg_rpm = np.mean(window_rpm)
            rpm_stability = 1.0 - (np.std(window_rpm) / max(avg_rpm, 1))  # 避免除零
            
            # 判断转速等级
            speed_label = None
            for label, (min_rpm, max_rpm) in self.speed_thresholds.items():
                if min_rpm <= avg_rpm < max_rpm:
                    speed_label = label
                    break
            
            if speed_label != current_speed_label:
                # 转速段发生变化
                if current_speed_label is not None and segment_start is not None:
                    # 结束上一个段
                    end_time = time[i]
                    confidence = max(0.6, min(0.95, rpm_stability))
                    
                    predictions.append(TimeseriesSpan(
                        start=segment_start,
                        end=end_time,
                        label_choice=current_speed_label,
                        label_group="speed_level"
                    ))
                
                # 开始新段
                current_speed_label = speed_label
                segment_start = time[i]
        
        # 处理最后一个段
        if current_speed_label is not None and segment_start is not None:
            end_time = time[-1]
            confidence = max(0.6, min(0.95, rpm_stability))
            
            predictions.append(TimeseriesSpan(
                start=segment_start,
                end=end_time,
                label_choice=current_speed_label,
                label_group="speed_level"
            ))
                    
        return predictions
    
    def predict_fault_type(self, data: pd.DataFrame, features: Dict) -> List[TimeseriesSpan]:
        """预测故障类型 - 基于振动特征进行故障诊断"""
        predictions = []
        time = data['time'] if 'time' in data.columns else np.arange(len(data)) * 0.001
        
        # 基于特征的故障检测逻辑
        fault_scores = {}
        
        # 不平衡检测 - 基于振动幅值
        unbalance_score = 0
        for axis in ['vibration_x', 'vibration_y', 'vibration_z']:
            rms_key = f'{axis}_rms'
            if rms_key in features:
                unbalance_score += min(1.0, features[rms_key] / 2.0)
        fault_scores['不平衡'] = unbalance_score / 3
        
        # 轴承故障检测 - 基于高频成分
        bearing_score = 0
        if 'dominant_freq' in features:
            bearing_score = min(1.0, features['dominant_freq'] / 1000)
        fault_scores['轴承故障'] = bearing_score
        
        # 齿轮故障检测 - 基于频谱特征
        gear_score = 0
        if 'spectral_centroid' in features:
            gear_score = min(1.0, features['spectral_centroid'] / 500)
        fault_scores['齿轮故障'] = gear_score
        
        # 判断故障类型
        max_fault = max(fault_scores.items(), key=lambda x: x[1])
        
        if max_fault[1] > 0.3:  # 故障阈值
            predictions.append(TimeseriesSpan(
                start=time[0],
                end=time[-1],
                label_choice=max_fault[0],
                label_group="fault_type"
            ))
        else:
            # 正常状态
            predictions.append(TimeseriesSpan(
                start=time[0],
                end=time[-1],
                label_choice='正常',
                label_group="fault_type"
            ))
            
        return predictions
    
    def predict_quality_score(self, features: Dict) -> Number:
        """预测设备健康质量分数 - 使用Number类型标注"""
        base_score = 100.0
        
        # 振动幅值影响 (权重: 40%)
        rms_penalty = 0
        for axis in ['vibration_x', 'vibration_y', 'vibration_z']:
            rms_key = f'{axis}_rms'
            if rms_key in features:
                rms_penalty += min(15, features[rms_key] * 7.5)
        
        # 频域特征影响 (权重: 30%)
        freq_penalty = 0
        if 'dominant_freq' in features:
            freq_penalty = min(15, features['dominant_freq'] / 100)
        
        # 峰值因子影响 (权重: 20%)
        peak_penalty = 0
        for axis in ['vibration_x', 'vibration_y', 'vibration_z']:
            crest_key = f'{axis}_crest_factor'
            if crest_key in features:
                # 峰值因子过高表示冲击
                if features[crest_key] > 5:
                    peak_penalty += min(10, (features[crest_key] - 5) * 2)
        
        # 转速稳定性影响 (权重: 10%)
        speed_penalty = 0
        if 'rpm_std' in features and 'rpm_mean' in features:
            rpm_cv = features['rpm_std'] / max(features['rpm_mean'], 1)
            speed_penalty = min(10, rpm_cv * 100)
        
        quality_score = max(0, base_score - rms_penalty - freq_penalty - peak_penalty - speed_penalty)
        
        # 计算置信度
        feature_count = len([k for k in features.keys() if 'rms' in k or 'freq' in k])
        confidence = min(0.95, 0.6 + feature_count * 0.05)
        
        return Number(
            value=quality_score,
            label_group='quality_score',
            label_target='ts'
        )
    
    def predict(self, task_data: pd.DataFrame, **kwargs) -> List:
        """主预测方法 - 返回多标签预测结果"""
        predictions = []
        
        # 提取特征
        features = self.extract_features(task_data)
        
        # 转速段预测
        speed_predictions = self.predict_speed_segments(task_data)
        predictions.extend(speed_predictions)
        
        # 故障类型预测
        fault_predictions = self.predict_fault_type(task_data, features)
        predictions.extend(fault_predictions)
        
        # 质量分数预测
        quality_prediction = self.predict_quality_score(features)
        predictions.append(quality_prediction)
        
        # 置信度预测
        overall_confidence = np.mean([0.8 for p in predictions])  # 简化置信度计算
        confidence_prediction = Number(
            value=overall_confidence,
            label_group='confidence_level',
            label_target='ts'
        )
        predictions.append(confidence_prediction)
        
        return predictions
