"""
音频处理工具模块

提供音频文件的加载、处理、特征提取和分段等功能
"""

import librosa
import soundfile as sf
import numpy as np
import requests
import tempfile
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AudioProcessor:
    """音频处理工具类，用于加载和处理音频文件"""
    
    def __init__(self, sample_rate=16000):
        """
        初始化音频处理器
        
        Args:
            sample_rate (int): 目标采样率，默认16000Hz
        """
        self.sample_rate = sample_rate
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.ogg']
        logger.info(f"AudioProcessor initialized with sample rate: {sample_rate}")
    
    def load_audio(self, audio_url):
        """
        从URL或本地路径加载音频文件
        
        Args:
            audio_url (str): 音频文件的URL或本地路径
            
        Returns:
            numpy.ndarray: 音频数据数组
            
        Raises:
            Exception: 加载失败时抛出异常
        """
        try:
            if audio_url.startswith('http'):
                # 从URL下载音频
                audio_data = self._download_and_load_audio(audio_url)
            else:
                # 加载本地音频文件
                audio_data = self._load_local_audio(audio_url)
            
            # 标准化音频
            audio_data = self._normalize_audio(audio_data)
            
            logger.info(f"Successfully loaded audio with shape: {audio_data.shape}")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error loading audio from {audio_url}: {str(e)}")
            raise
    
    def _download_and_load_audio(self, url):
        """
        从URL下载音频文件并加载
        
        Args:
            url (str): 音频文件URL
            
        Returns:
            numpy.ndarray: 音频数据数组
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            # 从临时文件加载音频
            audio_data, sr = librosa.load(temp_path, sr=self.sample_rate)
            
            # 清理临时文件
            os.unlink(temp_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error downloading audio from URL: {str(e)}")
            raise
    
    def _load_local_audio(self, file_path):
        """
        从本地文件路径加载音频
        
        Args:
            file_path (str): 本地音频文件路径
            
        Returns:
            numpy.ndarray: 音频数据数组
            
        Raises:
            FileNotFoundError: 文件不存在时抛出
            ValueError: 不支持的音频格式时抛出
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported audio format: {file_ext}")
        
        audio_data, sr = librosa.load(file_path, sr=self.sample_rate)
        return audio_data
    
    def _normalize_audio(self, audio_data):
        """
        标准化音频振幅
        
        Args:
            audio_data (numpy.ndarray): 音频数据
            
        Returns:
            numpy.ndarray: 标准化后的音频数据
        """
        if len(audio_data) == 0:
            return audio_data
        
        # 移除DC偏移
        audio_data = audio_data - np.mean(audio_data)
        
        # 标准化到[-1, 1]范围
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
        
        return audio_data
    
    def get_current_timestamp(self):
        """
        获取当前时间戳用于日志记录
        
        Returns:
            str: ISO格式的时间戳
        """
        return datetime.now().isoformat()
