"""
音频标注ML Backend模型

基于Label Studio ML Backend架构，实现音频标注的AI预测服务
"""

from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
import os
import logging
from audio_predictor import AudioPredictor
from audio_utils import AudioProcessor

logger = logging.getLogger(__name__)


class AudioAnnotationModel(LabelStudioMLBase):
    """音频标注任务的ML Backend模型"""
    
    def setup(self):
        """配置音频标注模型参数"""
        self.set("model_version", "audio_annotation_v1.0")
        
        # 初始化音频处理器和预测器
        self.audio_processor = AudioProcessor()
        self.audio_predictor = AudioPredictor()
        
        # 不同标注类型的配置
        self.annotation_types = {
            "speech_recognition": {
                "label_group": "transcription",
                "label_name": "语音转文字"
            },
            "audio_classification": {
                "label_group": "audio_type",
                "label_name": "音频类型"
            }
        }
        
        logger.info("Audio annotation model initialized successfully")

    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        """
        执行音频标注预测
        
        Args:
            tasks: Label Studio任务，包含音频数据
            context: Label Studio的额外上下文
            **kwargs: 其他参数
            
        Returns:
            ModelResponse: 包含音频标注的模型响应
        """
        logger.info(f"Processing {len(tasks)} audio annotation tasks")
        
        predictions = []
        
        for task in tasks:
            try:
                # 从任务数据中提取音频URL
                audio_url = task['data'].get('audio')
                if not audio_url:
                    logger.warning(f"No audio URL found in task {task.get('id', 'unknown')}")
                    continue
                
                # 处理音频文件
                audio_data = self.audio_processor.load_audio(audio_url)
                
                # 为不同标注类型生成预测
                task_predictions = []
                
                # 语音识别
                transcription = self.audio_predictor.transcribe_audio(audio_data)
                if transcription:
                    task_predictions.extend(self._format_transcription_results(transcription))
                
                # 音频分类
                audio_type = self.audio_predictor.classify_audio(audio_data)
                if audio_type:
                    task_predictions.extend(self._format_classification_results(audio_type))
                
                predictions.append({"result": task_predictions})
                
            except Exception as e:
                logger.error(f"Error processing task {task.get('id', 'unknown')}: {str(e)}")
                predictions.append({"result": []})
        
        return ModelResponse(
            model_version=self.get("model_version"),
            predictions=predictions
        )
    
    def _format_transcription_results(self, transcription_data):
        """格式化语音识别结果为Label Studio格式"""
        results = []
        for segment in transcription_data:
            results.append({
                "from_name": "transcription",
                "to_name": "audio",
                "type": "textarea",
                "value": {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": [segment["text"]]
                }
            })
        return results
    
    def _format_classification_results(self, classification_data):
        """格式化音频分类结果为Label Studio格式"""
        return [{
            "from_name": "audio_type",
            "to_name": "audio",
            "type": "choices",
            "value": {
                "choices": [classification_data["label"]]
            }
        }]
    
    def fit(self, event, data, **kwargs):
        """处理标注更新事件"""
        logger.info(f"Received fit event: {event}")
        try:
            # 记录事件
            annotation_history = self.get('annotation_history', [])
            annotation_entry = {
                'event': event,
                'timestamp': self.audio_processor.get_current_timestamp(),
                'project_id': data.get('project', {}).get('id'),
                'task_id': data.get('task', {}).get('id'),
                'annotation_id': data.get('annotation', {}).get('id'),
                'user_id': data.get('annotation', {}).get('completed_by')
            }
            annotation_history.append(annotation_entry)
            
            # 保持历史记录在合理范围内
            if len(annotation_history) > 1000:
                annotation_history = annotation_history[-1000:]
            
            self.set('annotation_history', annotation_history)
            logger.info(f"Fit event {event} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing fit event {event}: {str(e)}")
