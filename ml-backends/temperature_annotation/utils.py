"""
数据工具模块

提供温度数据的加载、处理和工具函数
"""

import pandas as pd
import requests
import concurrent.futures
from typing import Dict, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


def load_data(urls: Dict[int, str]) -> Dict[int, pd.DataFrame]:
    """
    并发加载温度数据
    
    Args:
        urls: 炮号到URL的映射字典
        
    Returns:
        炮号到数据DataFrame的映射字典
    """
    def fetch_csv(shot_url_pair):
        shot, url = shot_url_pair
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            df = pd.read_csv(pd.StringIO(response.text))
            logger.info(f"成功加载炮号 {shot} 的数据，形状: {df.shape}")
            return shot, df
        except Exception as e:
            logger.error(f"加载炮号 {shot} 数据失败: {e}")
            return shot, None
    
    data_dict = {}
    logger.info(f"开始加载 {len(urls)} 个炮号的数据")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(fetch_csv, urls.items())
        
    for shot, df in results:
        if df is not None:
            data_dict[shot] = df
            
    logger.info(f"成功加载 {len(data_dict)} 个炮号的数据")
    return data_dict


def validate_temperature_data(df: pd.DataFrame, required_columns: list = None) -> bool:
    """
    验证温度数据的有效性
    
    Args:
        df: 温度数据DataFrame
        required_columns: 必需的列名列表
        
    Returns:
        数据是否有效
    """
    if df is None or df.empty:
        logger.warning("数据为空")
        return False
    
    if required_columns:
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"缺少必需的列: {missing_columns}")
            return False
    
    # 检查时间列
    if 'time' not in df.columns:
        logger.warning("缺少时间列")
        return False
    
    # 检查时间数据的单调性
    time_data = df['time'].values
    if not np.all(np.diff(time_data) >= 0):
        logger.warning("时间数据不是单调递增的")
        return False
    
    # 检查数值列的有效性
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    for col in numeric_columns:
        if col == 'time':
            continue
        if df[col].isnull().all():
            logger.warning(f"列 {col} 全为空值")
            return False
    
    logger.info("温度数据验证通过")
    return True


def preprocess_temperature_data(df: pd.DataFrame, 
                              remove_outliers: bool = True,
                              outlier_threshold: float = 3.0,
                              interpolate_missing: bool = True) -> pd.DataFrame:
    """
    预处理温度数据
    
    Args:
        df: 原始温度数据
        remove_outliers: 是否移除异常值
        outlier_threshold: 异常值检测阈值（标准差倍数）
        interpolate_missing: 是否插值缺失值
        
    Returns:
        预处理后的数据
    """
    df_processed = df.copy()
    
    # 插值缺失值
    if interpolate_missing:
        numeric_columns = df_processed.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if col == 'time':
                continue
            if df_processed[col].isnull().any():
                df_processed[col] = df_processed[col].interpolate(method='linear')
                logger.info(f"列 {col} 的缺失值已插值")
    
    # 移除异常值
    if remove_outliers:
        numeric_columns = df_processed.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if col == 'time':
                continue
            
            # 计算统计量
            mean_val = df_processed[col].mean()
            std_val = df_processed[col].std()
            
            # 标记异常值
            outlier_mask = np.abs(df_processed[col] - mean_val) > outlier_threshold * std_val
            outlier_count = outlier_mask.sum()
            
            if outlier_count > 0:
                # 将异常值替换为均值
                df_processed.loc[outlier_mask, col] = mean_val
                logger.info(f"列 {col} 移除了 {outlier_count} 个异常值")
    
    return df_processed


def extract_temperature_channels(df: pd.DataFrame, 
                               channel_patterns: list = None) -> list:
    """
    提取温度通道列名
    
    Args:
        df: 温度数据DataFrame
        channel_patterns: 通道名称模式列表
        
    Returns:
        温度通道列名列表
    """
    if channel_patterns is None:
        channel_patterns = ['Te', 'temp', 'Ti', 'temperature']
    
    temperature_channels = []
    for col in df.columns:
        col_lower = col.lower()
        if any(pattern.lower() in col_lower for pattern in channel_patterns):
            temperature_channels.append(col)
    
    logger.info(f"找到 {len(temperature_channels)} 个温度通道: {temperature_channels}")
    return temperature_channels


def calculate_temperature_statistics(df: pd.DataFrame, 
                                   temperature_channels: list = None) -> Dict:
    """
    计算温度统计信息
    
    Args:
        df: 温度数据DataFrame
        temperature_channels: 温度通道列表
        
    Returns:
        统计信息字典
    """
    if temperature_channels is None:
        temperature_channels = extract_temperature_channels(df)
    
    stats = {}
    for channel in temperature_channels:
        if channel in df.columns:
            channel_data = df[channel].dropna()
            if len(channel_data) > 0:
                stats[channel] = {
                    'mean': float(channel_data.mean()),
                    'std': float(channel_data.std()),
                    'min': float(channel_data.min()),
                    'max': float(channel_data.max()),
                    'count': len(channel_data)
                }
    
    logger.info(f"计算了 {len(stats)} 个通道的统计信息")
    return stats


def normalize_temperature_data(df: pd.DataFrame, 
                              temperature_channels: list = None,
                              method: str = 'zscore') -> pd.DataFrame:
    """
    标准化温度数据
    
    Args:
        df: 温度数据DataFrame
        temperature_channels: 温度通道列表
        method: 标准化方法 ('zscore', 'minmax', 'robust')
        
    Returns:
        标准化后的数据
    """
    if temperature_channels is None:
        temperature_channels = extract_temperature_channels(df)
    
    df_normalized = df.copy()
    
    for channel in temperature_channels:
        if channel in df_normalized.columns:
            channel_data = df_normalized[channel].dropna()
            if len(channel_data) > 0:
                if method == 'zscore':
                    # Z-score标准化
                    mean_val = channel_data.mean()
                    std_val = channel_data.std()
                    if std_val > 0:
                        df_normalized[channel] = (df_normalized[channel] - mean_val) / std_val
                
                elif method == 'minmax':
                    # Min-Max标准化
                    min_val = channel_data.min()
                    max_val = channel_data.max()
                    if max_val > min_val:
                        df_normalized[channel] = (df_normalized[channel] - min_val) / (max_val - min_val)
                
                elif method == 'robust':
                    # 稳健标准化（基于中位数和四分位距）
                    median_val = channel_data.median()
                    q75 = channel_data.quantile(0.75)
                    q25 = channel_data.quantile(0.25)
                    iqr = q75 - q25
                    if iqr > 0:
                        df_normalized[channel] = (df_normalized[channel] - median_val) / iqr
                
                logger.info(f"通道 {channel} 已使用 {method} 方法标准化")
    
    return df_normalized


def segment_temperature_data(df: pd.DataFrame, 
                            segment_length: float = 1.0,
                            overlap: float = 0.0) -> list:
    """
    分段温度数据
    
    Args:
        df: 温度数据DataFrame
        segment_length: 段长度（秒）
        overlap: 重叠比例（0-1）
        
    Returns:
        数据段列表
    """
    segments = []
    time_data = df['time'].values
    
    if len(time_data) < 2:
        return segments
    
    # 计算时间步长
    time_step = time_data[1] - time_data[0]
    segment_samples = int(segment_length / time_step)
    overlap_samples = int(segment_samples * overlap)
    hop_samples = segment_samples - overlap_samples
    
    for i in range(0, len(df) - segment_samples + 1, hop_samples):
        segment_df = df.iloc[i:i + segment_samples].copy()
        segment_start = time_data[i]
        segment_end = time_data[i + segment_samples - 1]
        
        segments.append({
            'data': segment_df,
            'start_time': segment_start,
            'end_time': segment_end,
            'segment_index': i // hop_samples
        })
    
    logger.info(f"将数据分为 {len(segments)} 段，每段长度 {segment_length} 秒")
    return segments
