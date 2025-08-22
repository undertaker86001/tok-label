"""
温度预测器模块

实现温度特征识别算法，包括温度上升、下降、峰值检测等
"""

import pandas as pd
import numpy as np
from typing import List
from prediction import BasePredictor, Prediction
from prediction import start_end_time_1D, detect_temperature_anomalies, find_temperature_peaks
import logging

logger = logging.getLogger(__name__)


class TemperaturePredictor(BasePredictor):
    """温度预测器类"""
    
    def __init__(self, 
                 label_group: str = 'temperature_events', 
                 temp_rise_threshold: float = 1000.0,  # eV
                 temp_fall_threshold: float = 500.0,   # eV
                 gradient_threshold: float = 100.0,    # eV/ms
                 anomaly_threshold: float = 3.0,       # 异常检测阈值
                 min_peak_height: float = 800.0):      # 最小峰值高度
        """
        初始化温度预测器
        
        Args:
            label_group: 标签组名称
            temp_rise_threshold: 温度上升阈值
            temp_fall_threshold: 温度下降阈值
            gradient_threshold: 梯度阈值
            anomaly_threshold: 异常检测阈值
            min_peak_height: 最小峰值高度
        """
        super().__init__()
        self.label_group = label_group
        self.temp_rise_threshold = temp_rise_threshold
        self.temp_fall_threshold = temp_fall_threshold
        self.gradient_threshold = gradient_threshold
        self.anomaly_threshold = anomaly_threshold
        self.min_peak_height = min_peak_height
        
        logger.info(f"温度预测器初始化完成，标签组: {label_group}")
        logger.info(f"阈值设置: 上升={temp_rise_threshold}, 下降={temp_fall_threshold}, 梯度={gradient_threshold}")
    
    def user_predict(self, task_data: pd.DataFrame) -> List[Prediction]:
        """
        执行温度预测
        
        Args:
            task_data: 任务数据，包含时间序列温度数据
            
        Returns:
            预测结果列表
        """
        predictions = []
        
        try:
            # 验证数据
            if task_data is None or task_data.empty:
                logger.warning("任务数据为空")
                return predictions
            
            if 'time' not in task_data.columns:
                logger.warning("缺少时间列")
                return predictions
            
            time = task_data['time'].values
            
            # 检测多个温度通道
            temp_channels = self._extract_temperature_channels(task_data)
            
            if not temp_channels:
                logger.warning("未找到温度通道")
                return predictions
            
            logger.info(f"开始分析 {len(temp_channels)} 个温度通道: {temp_channels}")
            
            for channel in temp_channels:
                if channel not in task_data.columns:
                    continue
                    
                temp_data = np.array(task_data[channel])
                
                # 跳过全为NaN的通道
                if np.all(np.isnan(temp_data)):
                    logger.warning(f"通道 {channel} 全为NaN，跳过")
                    continue
                
                # 处理NaN值
                temp_data = self._handle_missing_values(temp_data)
                
                # 1. 检测温度上升阶段
                rise_predictions = self._detect_rise_phases(time, temp_data, channel)
                predictions.extend(rise_predictions)
                
                # 2. 检测温度峰值时刻
                peak_predictions = self._detect_peak_moments(time, temp_data, channel)
                predictions.extend(peak_predictions)
                
                # 3. 检测温度下降阶段
                fall_predictions = self._detect_fall_phases(time, temp_data, channel)
                predictions.extend(fall_predictions)
                
                # 4. 检测异常温度事件
                anomaly_predictions = self._detect_anomalies(time, temp_data, channel)
                predictions.extend(anomaly_predictions)
                
                # 5. 检测温度平台期
                plateau_predictions = self._detect_plateau_phases(time, temp_data, channel)
                predictions.extend(plateau_predictions)
            
            logger.info(f"温度预测完成，生成了 {len(predictions)} 个预测结果")
            
        except Exception as e:
            logger.error(f"温度预测过程中出错: {str(e)}")
        
        return predictions
    
    def _extract_temperature_channels(self, task_data: pd.DataFrame) -> List[str]:
        """提取温度通道列名"""
        temp_channels = []
        for col in task_data.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in ['te', 'temp', 'ti', 'temperature']):
                temp_channels.append(col)
        return temp_channels
    
    def _handle_missing_values(self, temp_data: np.ndarray) -> np.ndarray:
        """处理缺失值"""
        # 使用前向填充处理NaN值
        temp_data_clean = temp_data.copy()
        for i in range(1, len(temp_data_clean)):
            if np.isnan(temp_data_clean[i]):
                temp_data_clean[i] = temp_data_clean[i-1]
        
        # 如果第一个值是NaN，使用下一个非NaN值
        if np.isnan(temp_data_clean[0]):
            for i in range(1, len(temp_data_clean)):
                if not np.isnan(temp_data_clean[i]):
                    temp_data_clean[0] = temp_data_clean[i]
                    break
        
        return temp_data_clean
    
    def _detect_rise_phases(self, time: np.ndarray, temp_data: np.ndarray, channel: str) -> List[Prediction]:
        """检测温度上升阶段"""
        predictions = []
        
        try:
            # 检测温度上升区间
            rise_intervals = start_end_time_1D(
                temp_data, self.temp_rise_threshold, postive=True
            )
            
            for start_idx, end_idx in rise_intervals:
                if start_idx < end_idx:  # 确保区间有效
                    start_time = time[start_idx]
                    end_time = time[end_idx]
                    
                    # 计算上升阶段的特征
                    rise_temp_data = temp_data[start_idx:end_idx+1]
                    max_temp = np.max(rise_temp_data)
                    avg_temp = np.mean(rise_temp_data)
                    
                    # 根据温度特征调整标签
                    if max_temp > self.temp_rise_threshold * 1.5:
                        label = f"{channel}_快速上升"
                    else:
                        label = f"{channel}_上升阶段"
                    
                    predictions.append(Prediction(
                        self.label_group, 
                        label, 
                        start=start_time, 
                        end=end_time,
                        score=min(0.9, (max_temp - self.temp_rise_threshold) / self.temp_rise_threshold)
                    ))
            
            logger.info(f"通道 {channel} 检测到 {len(predictions)} 个上升阶段")
            
        except Exception as e:
            logger.error(f"检测通道 {channel} 上升阶段时出错: {str(e)}")
        
        return predictions
    
    def _detect_peak_moments(self, time: np.ndarray, temp_data: np.ndarray, channel: str) -> List[Prediction]:
        """检测温度峰值时刻"""
        predictions = []
        
        try:
            # 查找温度峰值
            peak_times = find_temperature_peaks(
                temp_data, time, 
                gradient_threshold=self.gradient_threshold,
                min_peak_height=self.min_peak_height
            )
            
            for peak_time in peak_times:
                # 找到峰值对应的时间索引
                peak_idx = np.argmin(np.abs(time - peak_time))
                peak_temp = temp_data[peak_idx]
                
                # 根据峰值高度调整标签
                if peak_temp > self.temp_rise_threshold * 2:
                    label = f"{channel}_极高峰值"
                elif peak_temp > self.temp_rise_threshold * 1.5:
                    label = f"{channel}_高峰值"
                else:
                    label = f"{channel}_峰值时刻"
                
                predictions.append(Prediction(
                    self.label_group,
                    label,
                    start=peak_time,
                    end=None,  # 时间点标注
                    score=min(0.95, peak_temp / (self.temp_rise_threshold * 2))
                ))
            
            logger.info(f"通道 {channel} 检测到 {len(predictions)} 个峰值时刻")
            
        except Exception as e:
            logger.error(f"检测通道 {channel} 峰值时刻时出错: {str(e)}")
        
        return predictions
    
    def _detect_fall_phases(self, time: np.ndarray, temp_data: np.ndarray, channel: str) -> List[Prediction]:
        """检测温度下降阶段"""
        predictions = []
        
        try:
            # 检测温度下降区间
            fall_intervals = start_end_time_1D(
                temp_data, self.temp_fall_threshold, postive=False
            )
            
            for start_idx, end_idx in fall_intervals:
                if start_idx < end_idx:  # 确保区间有效
                    start_time = time[start_idx]
                    end_time = time[end_idx]
                    
                    # 计算下降阶段的特征
                    fall_temp_data = temp_data[start_idx:end_idx+1]
                    min_temp = np.min(fall_temp_data)
                    avg_temp = np.mean(fall_temp_data)
                    
                    # 根据温度特征调整标签
                    if min_temp < self.temp_fall_threshold * 0.5:
                        label = f"{channel}_快速下降"
                    else:
                        label = f"{channel}_下降阶段"
                    
                    predictions.append(Prediction(
                        self.label_group,
                        label,
                        start=start_time,
                        end=end_time,
                        score=min(0.9, (self.temp_fall_threshold - min_temp) / self.temp_fall_threshold)
                    ))
            
            logger.info(f"通道 {channel} 检测到 {len(predictions)} 个下降阶段")
            
        except Exception as e:
            logger.error(f"检测通道 {channel} 下降阶段时出错: {str(e)}")
        
        return predictions
    
    def _detect_anomalies(self, time: np.ndarray, temp_data: np.ndarray, channel: str) -> List[Prediction]:
        """检测异常温度事件"""
        predictions = []
        
        try:
            # 检测温度异常
            anomalies = detect_temperature_anomalies(
                temp_data, time, 
                threshold=self.anomaly_threshold
            )
            
            for start_time, end_time, anomaly_type in anomalies:
                predictions.append(Prediction(
                    self.label_group,
                    f"{channel}_{anomaly_type}",
                    start=start_time,
                    end=end_time,
                    score=0.8  # 异常检测的置信度
                ))
            
            logger.info(f"通道 {channel} 检测到 {len(predictions)} 个异常事件")
            
        except Exception as e:
            logger.error(f"检测通道 {channel} 异常事件时出错: {str(e)}")
        
        return predictions
    
    def _detect_plateau_phases(self, time: np.ndarray, temp_data: np.ndarray, channel: str) -> List[Prediction]:
        """检测温度平台期"""
        predictions = []
        
        try:
            # 计算温度梯度
            gradient = np.gradient(temp_data)
            
            # 检测梯度较小的区间（平台期）
            plateau_threshold = self.gradient_threshold * 0.1  # 平台期的梯度阈值
            plateau_mask = np.abs(gradient) < plateau_threshold
            
            # 找到连续的平台期区间
            plateau_intervals = start_end_time_1D(
                plateau_mask.astype(float), 0.5, postive=True
            )
            
            for start_idx, end_idx in plateau_intervals:
                if end_idx - start_idx > 10:  # 平台期至少持续10个采样点
                    start_time = time[start_idx]
                    end_time = time[end_idx]
                    
                    # 计算平台期的特征
                    plateau_temp_data = temp_data[start_idx:end_idx+1]
                    avg_temp = np.mean(plateau_temp_data)
                    temp_std = np.std(plateau_temp_data)
                    
                    # 根据温度水平调整标签
                    if avg_temp > self.temp_rise_threshold:
                        label = f"{channel}_高温平台期"
                    elif avg_temp > self.temp_fall_threshold:
                        label = f"{channel}_中温平台期"
                    else:
                        label = f"{channel}_低温平台期"
                    
                    # 根据稳定性计算置信度
                    stability_score = max(0.5, 1.0 - temp_std / avg_temp) if avg_temp > 0 else 0.5
                    
                    predictions.append(Prediction(
                        self.label_group,
                        label,
                        start=start_time,
                        end=end_time,
                        score=stability_score
                    ))
            
            logger.info(f"通道 {channel} 检测到 {len(predictions)} 个平台期")
            
        except Exception as e:
            logger.error(f"检测通道 {channel} 平台期时出错: {str(e)}")
        
        return predictions
    
    def update_thresholds(self, new_thresholds: dict):
        """更新阈值参数"""
        if 'temp_rise_threshold' in new_thresholds:
            self.temp_rise_threshold = new_thresholds['temp_rise_threshold']
        if 'temp_fall_threshold' in new_thresholds:
            self.temp_fall_threshold = new_thresholds['temp_fall_threshold']
        if 'gradient_threshold' in new_thresholds:
            self.gradient_threshold = new_thresholds['gradient_threshold']
        if 'anomaly_threshold' in new_thresholds:
            self.anomaly_threshold = new_thresholds['anomaly_threshold']
        if 'min_peak_height' in new_thresholds:
            self.min_peak_height = new_thresholds['min_peak_height']
        
        logger.info(f"阈值参数已更新: {new_thresholds}")
    
    def get_current_thresholds(self) -> dict:
        """获取当前阈值参数"""
        return {
            'temp_rise_threshold': self.temp_rise_threshold,
            'temp_fall_threshold': self.temp_fall_threshold,
            'gradient_threshold': self.gradient_threshold,
            'anomaly_threshold': self.anomaly_threshold,
            'min_peak_height': self.min_peak_height
        }
