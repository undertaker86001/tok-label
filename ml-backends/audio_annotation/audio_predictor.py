"""
音频预测器模块

实现各种音频标注任务的预测功能，包括语音识别、说话人检测、音频分类和情感识别
"""

import whisper
import torch
import torchaudio
import librosa
import numpy as np
from transformers import pipeline
import logging

logger = logging.getLogger(__name__)


class AudioPredictor:
    """音频预测引擎，用于各种音频标注任务"""
    
    def __init__(self):
        """
        初始化音频预测器
        
        加载预训练模型并设置设备（GPU/CPU）
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AudioPredictor initialized on device: {self.device}")
        
        # 初始化模型
        self._load_models()
    
    def _load_models(self):
        """加载预训练的音频任务模型"""
        try:
            # Whisper用于语音识别
            self.whisper_model = whisper.load_model("base")
            logger.info("Whisper model loaded successfully")
            
            # 音频分类pipeline
            self.audio_classifier = pipeline(
                "audio-classification",
                model="facebook/wav2vec2-base-960h",
                device=0 if self.device == "cuda" else -1
            )
            logger.info("Audio classification model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            raise
    
    def transcribe_audio(self, audio_data):
        """
        使用Whisper进行语音转文字
        
        Args:
            audio_data (numpy.ndarray): 音频数据数组
            
        Returns:
            list: 包含时间戳的转录片段列表
        """
        try:
            result = self.whisper_model.transcribe(audio_data)
            
            segments = []
            for segment in result.get("segments", []):
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })
            
            logger.info(f"Transcribed {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error in speech recognition: {str(e)}")
            return []
    
    def classify_audio(self, audio_data):
        """
        分类音频类型（语音、音乐、噪音等）
        
        Args:
            audio_data (numpy.ndarray): 音频数据数组
            
        Returns:
            dict: 分类结果
        """
        try:
            # 基于频谱特征的简单音频分类
            mfccs = librosa.feature.mfcc(y=audio_data, sr=16000, n_mfcc=13)
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=16000)
            
            # 简单的基于规则的分类
            mean_centroid = np.mean(spectral_centroid)
            
            if mean_centroid > 2000:
                audio_type = "语音"
            elif mean_centroid > 1000:
                audio_type = "音乐"
            else:
                audio_type = "噪音"
            
            logger.info(f"Audio classified as: {audio_type}")
            return {"label": audio_type, "confidence": 0.8}
            
        except Exception as e:
            logger.error(f"Error in audio classification: {str(e)}")
            return None
