"""
温度标注ML Backend模型

基于Label Studio ML Backend架构，实现温度标注的AI预测服务
"""

from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
import prediction
import utils
import numpy as np
import pandas as pd
import logging
import time
from temperature_predictor import TemperaturePredictor

logger = logging.getLogger(__name__)


class TemperatureModel(LabelStudioMLBase):
    """温度标注ML Backend模型"""
    
    def setup(self):
        """配置模型参数"""
        self.set("model_version", "temperature_v1.0")
        
        # 初始化温度预测器
        self.predictor = TemperaturePredictor()
        
        # 记录模型统计信息
        self.set('training_count', 0)
        self.set('last_training_time', time.time())
        
        logger.info("温度标注模型初始化完成")
    
    def get_data(self, tasks: List[Dict]) -> Dict:
        """获取任务数据"""
        urls = {}
        for task in tasks:
            data = task['data']
            urls[data['shot']] = data['csv']
        
        logger.info(f"开始加载 {len(urls)} 个炮号的数据")
        data_dict = utils.load_data(urls)
        return data_dict
    
    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        """执行温度预测"""
        logger.info(f'运行温度预测，任务数量: {len(tasks)}')
        
        try:
            data_dict = self.get_data(tasks)
            model_preds = []
            
            for shot, data in data_dict.items():
                try:
                    # 验证数据
                    if not utils.validate_temperature_data(data):
                        logger.warning(f"炮号 {shot} 数据验证失败，跳过")
                        continue
                    
                    # 预处理数据
                    data_processed = utils.preprocess_temperature_data(data)
                    
                    # 执行预测
                    preds = prediction.convert_to_labelstudio_form(
                        self.predictor.user_predict(data_processed), 
                        'temperature_model_v1'
                    )
                    
                    if preds:
                        model_preds.extend(preds)
                        logger.info(f'炮号 {shot} 预测成功，生成 {len(preds)} 个预测结果')
                    else:
                        logger.info(f'炮号 {shot} 未生成预测结果')
                        
                except Exception as e:
                    logger.error(f'炮号 {shot} 预测失败: {e}')
                    continue
            
            logger.info(f"温度预测完成，总共生成 {len(model_preds)} 个预测结果")
            
        except Exception as e:
            logger.error(f"温度预测过程中出错: {e}")
            model_preds = []
        
        return ModelResponse(predictions=model_preds)
    
    def fit(self, event, data, **kwargs):
        """
        温度标注模型的训练/更新逻辑
        
        每次创建或更新标注时调用此方法来优化模型参数
        
        Args:
            event: 事件类型 ('ANNOTATION_CREATED', 'ANNOTATION_UPDATED', 'START_TRAINING')
            data: 来自webhook的数据载荷
        """
        logger.info(f'接收到温度标注训练事件: {event}')
        
        try:
            # 获取之前的模型参数
            old_temp_rise_threshold = self.get('temp_rise_threshold', 1000.0)
            old_temp_fall_threshold = self.get('temp_fall_threshold', 500.0)
            old_gradient_threshold = self.get('gradient_threshold', 100.0)
            old_model_version = self.get('model_version', 'temperature_v1.0')
            
            logger.info(f'当前模型参数: 上升阈值={old_temp_rise_threshold}, 下降阈值={old_temp_fall_threshold}, 梯度阈值={old_gradient_threshold}')
            
            # 处理标注数据以优化参数
            if event in ['ANNOTATION_CREATED', 'ANNOTATION_UPDATED'] and data:
                try:
                    # 解析标注数据
                    annotation_data = self._parse_annotation_data(data)
                    
                    if annotation_data:
                        # 基于标注数据调整阈值参数
                        new_thresholds = self._optimize_thresholds(annotation_data)
                        
                        # 更新预测器参数
                        if new_thresholds:
                            self.predictor.update_thresholds(new_thresholds)
                            
                            # 保存到缓存
                            self.set('temp_rise_threshold', self.predictor.temp_rise_threshold)
                            self.set('temp_fall_threshold', self.predictor.temp_fall_threshold)
                            self.set('gradient_threshold', self.predictor.gradient_threshold)
                            
                            # 更新模型版本
                            new_version = f"temperature_v1.0_{int(time.time())}"
                            self.set('model_version', new_version)
                            
                            logger.info(f'参数已更新: 上升阈值={self.predictor.temp_rise_threshold}, 下降阈值={self.predictor.temp_fall_threshold}, 梯度阈值={self.predictor.gradient_threshold}')
                            logger.info(f'模型版本更新为: {new_version}')
                        
                except Exception as e:
                    logger.error(f'处理标注数据时出错: {e}')
            
            # 记录训练统计信息
            training_count = self.get('training_count', 0) + 1
            self.set('training_count', training_count)
            self.set('last_training_time', time.time())
            
            logger.info(f'温度标注模型训练完成，总训练次数: {training_count}')
            
        except Exception as e:
            logger.error(f'温度标注模型训练过程中出错: {e}')
    
    def _parse_annotation_data(self, data):
        """解析标注数据，提取温度相关信息"""
        try:
            if 'annotation' in data and 'result' in data['annotation']:
                results = data['annotation']['result']
                temp_annotations = []
                
                for result in results:
                    if (result.get('from_name') == 'temperature_events' and   
                        result.get('type') == 'timeserieslabels'):
                        
                        value = result.get('value', {})
                        temp_annotations.append({
                            'label': value.get('timeserieslabels', [''])[0],
                            'start': value.get('start'),
                            'end': value.get('end'),
                            'shot': data.get('task', {}).get('data', {}).get('shot')
                        })
                
                logger.info(f"解析到 {len(temp_annotations)} 个温度标注")
                return temp_annotations if temp_annotations else None
                
        except Exception as e:
            logger.error(f'解析标注数据失败: {e}')
            return None
    
    def _optimize_thresholds(self, annotation_data):
        """基于标注数据优化阈值参数"""
        try:
            # 统计不同类型标注的特征
            rise_annotations = [ann for ann in annotation_data if '上升' in ann['label']]
            fall_annotations = [ann for ann in annotation_data if '下降' in ann['label']]
            peak_annotations = [ann for ann in annotation_data if '峰值' in ann['label']]
            
            new_thresholds = {}
            
            # 基于标注数据调整阈值（简化的自适应逻辑）
            if rise_annotations:
                # 如果有上升阶段标注，可以适当降低上升阈值以提高敏感度
                current_rise = self.get('temp_rise_threshold', 1000.0)
                new_thresholds['temp_rise_threshold'] = max(800.0, current_rise * 0.95)
                
            if fall_annotations:
                # 如果有下降阶段标注，可以适当调整下降阈值
                current_fall = self.get('temp_fall_threshold', 500.0)
                new_thresholds['temp_fall_threshold'] = max(400.0, current_fall * 0.95)
                
            if peak_annotations:
                # 如果有峰值标注，可以调整梯度阈值
                current_gradient = self.get('gradient_threshold', 100.0)
                new_thresholds['gradient_threshold'] = max(50.0, current_gradient * 0.9)
            
            if new_thresholds:
                logger.info(f"基于标注数据优化阈值: {new_thresholds}")
            
            return new_thresholds if new_thresholds else None
            
        except Exception as e:
            logger.error(f'优化阈值参数失败: {e}')
            return None
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            'model_version': self.get('model_version', 'temperature_v1.0'),
            'training_count': self.get('training_count', 0),
            'last_training_time': self.get('last_training_time', 0),
            'current_thresholds': self.predictor.get_current_thresholds()
        }
    
    def reset_model(self):
        """重置模型参数到默认值"""
        try:
            # 重置预测器参数
            self.predictor = TemperaturePredictor()
            
            # 重置模型版本
            self.set('model_version', 'temperature_v1.0')
            self.set('training_count', 0)
            self.set('last_training_time', time.time())
            
            logger.info("模型参数已重置到默认值")
            
        except Exception as e:
            logger.error(f"重置模型参数失败: {e}")
    
    def update_model_config(self, config: Dict):
        """更新模型配置"""
        try:
            if 'thresholds' in config:
                self.predictor.update_thresholds(config['thresholds'])
                logger.info(f"模型阈值已更新: {config['thresholds']}")
            
            if 'model_version' in config:
                self.set('model_version', config['model_version'])
                logger.info(f"模型版本已更新: {config['model_version']}")
            
        except Exception as e:
            logger.error(f"更新模型配置失败: {e}")
    
    def health_check(self) -> Dict:
        """健康检查"""
        try:
            return {
                'status': 'healthy',
                'model_version': self.get('model_version', 'unknown'),
                'predictor_initialized': hasattr(self, 'predictor'),
                'last_training': self.get('last_training_time', 0),
                'training_count': self.get('training_count', 0)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
