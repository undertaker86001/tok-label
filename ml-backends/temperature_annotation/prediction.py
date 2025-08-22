"""
温度预测工具模块

提供温度预测结果数据结构、预测器抽象基类和格式转换功能
"""

import abc
import pandas as pd
import numpy as np
from typing import List, Optional


class Prediction:
    """温度预测结果数据结构"""
    
    def __init__(self, label_group: str, label: str, start: float, end: Optional[float] = None, score: Optional[float] = None):
        """
        初始化温度预测结果
        
        Args:
            label_group: 标签组名称
            label: 标签名称
            start: 开始时间
            end: 结束时间（可选，None表示时间点）
            score: 置信度分数（可选）
        """
        self.label_group = label_group
        self.label = label
        self.start = start
        self.end = end
        self.score = score

    def __repr__(self):
        """字符串表示"""
        return f"<TemperaturePrediction label={self.label}, start={self.start}, end={self.end}>"


class BasePredictor(abc.ABC):
    """温度预测器抽象基类"""
    
    @abc.abstractmethod
    def user_predict(self, task_data: pd.DataFrame) -> List[Prediction]:
        """
        执行温度预测
        
        Args:
            task_data: 任务数据，包含时间序列温度数据
            
        Returns:
            预测结果列表
        """
        pass


def start_end_time_1D(predict_result, threshold: float, postive: bool = True):
    """
    1D温度数据阈值检测
    
    Args:
        predict_result: 温度数据数组
        threshold: 阈值
        postive: True表示检测大于阈值的区间，False表示检测小于阈值的区间
        
    Returns:
        区间列表，每个元素为(start_index, end_index)的元组
    """
    predict_result = np.array(predict_result)
    
    if postive:
        mask = predict_result > threshold
    else:
        mask = predict_result < threshold
        
    diff = np.diff(mask.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1
    
    if mask[0]:
        starts = np.insert(starts, 0, 0)
    if mask[-1]:
        ends = np.append(ends, len(predict_result) - 1)
        
    return list(zip(starts, ends))


def start_end_time(predict_result, threshold, postive: bool = True, all_dim: bool = True, time_axis: int = -1):
    """
    多维温度数据阈值检测
    
    Args:
        predict_result: 温度数据数组
        threshold: 阈值
        postive: True表示检测大于阈值的区间，False表示检测小于阈值的区间
        all_dim: True表示所有维度必须同时满足阈值条件，False表示对每个通道逐一判断
        time_axis: 时间轴索引
        
    Returns:
        区间列表，每个元素为(start_index, end_index)的元组
    """
    predict_result = np.array(predict_result)
    
    if postive:
        mask = predict_result > threshold
    else:
        mask = predict_result < threshold
    
    if all_dim:
        # 所有维度同时满足条件
        mask = np.all(mask, axis=tuple(i for i in range(mask.ndim) if i != time_axis))
    
    diff = np.diff(mask.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1
    
    if mask[0]:
        starts = np.insert(starts, 0, 0)
    if mask[-1]:
        ends = np.append(ends, len(mask) - 1)
        
    return list(zip(starts, ends))


def convert_to_labelstudio_form(pred_results: List[Prediction], model_version: str = "temperature_v1") -> List[dict]:
    """
    转换为Label Studio格式
    
    Args:
        pred_results: 预测结果列表
        model_version: 模型版本
        
    Returns:
        Label Studio格式的预测结果
    """
    LS_result_list = []
    
    for p in pred_results:
        if p.end is None:
            p.end = p.start
            
        LS_result_list.append({
            "from_name": p.label_group,
            "to_name": "ts",
            "type": "timeserieslabels",
            "value": {
                "start": p.start,
                "end": p.end,
                "timeserieslabels": [p.label]
            }
        })
    
    return [{
        "model_version": model_version,
        "result": LS_result_list
    }] if LS_result_list else []


def detect_temperature_anomalies(temp_data: np.ndarray, time_data: np.ndarray, 
                                threshold: float = 3.0, window_size: int = 10):
    """
    检测温度异常事件
    
    Args:
        temp_data: 温度数据
        time_data: 时间数据
        threshold: 异常检测阈值（标准差倍数）
        window_size: 滑动窗口大小
        
    Returns:
        异常事件列表，每个元素为(start_time, end_time, anomaly_type)的元组
    """
    anomalies = []
    
    # 计算滑动窗口的统计量
    for i in range(window_size, len(temp_data)):
        window_data = temp_data[i-window_size:i]
        mean_temp = np.mean(window_data)
        std_temp = np.std(window_data)
        
        current_temp = temp_data[i]
        
        # 检测异常（超出阈值范围）
        if abs(current_temp - mean_temp) > threshold * std_temp:
            anomaly_type = "温度突变" if current_temp > mean_temp else "温度骤降"
            anomalies.append((time_data[i], time_data[i], anomaly_type))
    
    return anomalies


def calculate_temperature_gradient(temp_data: np.ndarray, time_data: np.ndarray, 
                                 window_size: int = 5):
    """
    计算温度梯度
    
    Args:
        temp_data: 温度数据
        time_data: 时间数据
        window_size: 梯度计算窗口大小
        
    Returns:
        梯度数据数组
    """
    gradient = np.zeros_like(temp_data)
    
    for i in range(window_size, len(temp_data) - window_size):
        # 使用中心差分计算梯度
        temp_diff = temp_data[i + window_size] - temp_data[i - window_size]
        time_diff = time_data[i + window_size] - time_data[i - window_size]
        
        if time_diff != 0:
            gradient[i] = temp_diff / time_diff
    
    return gradient


def find_temperature_peaks(temp_data: np.ndarray, time_data: np.ndarray, 
                          gradient_threshold: float = 100.0, min_peak_height: float = 0.0):
    """
    查找温度峰值
    
    Args:
        temp_data: 温度数据
        time_data: 时间数据
        gradient_threshold: 梯度阈值
        min_peak_height: 最小峰值高度
        
    Returns:
        峰值时间列表
    """
    peaks = []
    gradient = calculate_temperature_gradient(temp_data, time_data)
    
    for i in range(1, len(gradient) - 1):
        # 梯度从正变负，且温度值足够高
        if (gradient[i-1] > gradient_threshold and 
            gradient[i+1] < -gradient_threshold and
            temp_data[i] > min_peak_height):
            peaks.append(time_data[i])
    
    return peaks
