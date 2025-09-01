from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
from toklabel import utils, prediction
import requests
import os
import json
import numpy as np
import pandas as pd
from predictor import VibrationPredictor

class VibrationPHMModel(LabelStudioMLBase):
    """振动数据PHM预测性维护ML后端模型"""
    
    def setup(self):
        """配置模型参数"""
        self.set("model_version", "vibration_phm_v1.0")
        self.predictor = VibrationPredictor()
        
        # 标签组配置
        self.label_groups = {
            'speed_level': ['低转速', '中转速', '高转速'],
            'fault_type': ['正常', '不平衡', '轴承故障', '齿轮故障'],
            'quality_score': 'number',
            'confidence_level': 'number'
        }
    
    def get_data(self, tasks: List[Dict]) -> Dict:
        """获取振动数据"""
        urls = {}
        for task in tasks:
            data = task['data']
            urls[data['shot']] = data['csv']
        return utils.load_data(urls)
    
    def convert_predictions_to_labelstudio(self, predictions: List, shot: int) -> List[Dict]:
        """转换预测结果为Label Studio格式"""
        ls_results = []
        
        for pred in predictions:
            if isinstance(pred, prediction.TimeseriesSpan):
                # 时间序列标注
                result = {
                    "from_name": pred.label_group,
                    "to_name": "ts",
                    "type": "timeserieslabels",
                    "value": {
                        "start": pred.start,
                        "end": pred.end,
                        "timeserieslabels": [pred.label_choice]
                    },
                    "score": 0.8  # 默认置信度
                }
                ls_results.append(result)
                
            elif isinstance(pred, prediction.Number):
                # 数值标注
                result = {
                    "from_name": pred.label_group,
                    "to_name": pred.label_target,
                    "type": "number",
                    "value": {
                        "number": pred.value
                    },
                    "score": 0.8  # 默认置信度
                }
                ls_results.append(result)
                
        return ls_results
    
    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        """执行预测"""
        print(f'振动数据预测任务: {len(tasks)} 个任务')
        print(f'项目ID: {self.project_id}')
        
        # 获取数据
        data_dict = self.get_data(tasks)
        model_predictions = []
        
        for shot, vibration_data in data_dict.items():
            try:
                # 执行预测
                predictions = self.predictor.predict(vibration_data)
                
                # 转换为Label Studio格式
                ls_results = self.convert_predictions_to_labelstudio(predictions, shot)
                
                model_predictions.append({
                    "result": ls_results,
                    "score": np.mean([r.get('score', 0.8) for r in ls_results])
                })
                
                print(f'设备 {shot} 预测成功: {len(ls_results)} 个标注')
                
            except Exception as e:
                print(f'设备 {shot} 预测失败: {e}')
                model_predictions.append({"result": []})
        
        return ModelResponse(predictions=model_predictions)
    
    def fit(self, event, data, **kwargs):
        """在线学习 - 根据标注数据更新模型"""
        print(f'收到标注事件: {event}')
        
        if event in ['ANNOTATION_CREATED', 'ANNOTATION_UPDATED']:
            # 获取标注数据
            annotation_data = data.get('annotation', {})
            task_data = data.get('task', {})
            
            # 提取标注特征用于模型更新
            self._update_model_with_annotation(annotation_data, task_data)
            
        elif event == 'START_TRAINING':
            # 批量训练模式
            self._batch_training()
            
        print('模型更新完成')
    
    def _update_model_with_annotation(self, annotation: Dict, task: Dict):
        """使用单个标注更新模型"""
        # 实现增量学习逻辑
        shot = task.get('data', {}).get('shot')
        if not shot:
            return
            
        # 缓存标注数据用于后续批量训练
        cached_annotations = self.get('cached_annotations', [])
        cached_annotations.append({
            'shot': shot,
            'annotation': annotation,
            'timestamp': annotation.get('updated_at')
        })
        
        # 限制缓存大小
        if len(cached_annotations) > 1000:
            cached_annotations = cached_annotations[-1000:]
            
        self.set('cached_annotations', cached_annotations)
    
    def _batch_training(self):
        """批量训练模型"""
        cached_annotations = self.get('cached_annotations', [])
        if len(cached_annotations) < 10:
            print('标注数据不足，跳过训练')
            return
            
        # 实现批量训练逻辑
        print(f'使用 {len(cached_annotations)} 个标注样本进行模型训练')
        
        # 提取训练特征和标签
        training_features = []
        training_labels = []
        
        for cached_anno in cached_annotations:
            try:
                # 获取原始数据
                shot = cached_anno['shot']
                data_url = self._get_data_url(shot)
                if not data_url:
                    continue
                    
                vibration_data = pd.read_csv(data_url)
                features = self.predictor.extract_features(vibration_data)
                
                # 提取标注标签
                annotation = cached_anno['annotation']
                labels = self._extract_labels_from_annotation(annotation)
                
                training_features.append(features)
                training_labels.append(labels)
                
            except Exception as e:
                print(f'处理标注数据失败: {e}')
                continue
        
        if len(training_features) > 0:
            # 更新模型参数
            self._update_model_parameters(training_features, training_labels)
            print('模型训练完成')
        else:
            print('没有有效的训练数据')
    
    def _get_data_url(self, shot: int) -> Optional[str]:
        """获取数据URL"""
        try:
            # 从Redis获取数据URL
            redis_key = f"vibration_phm:{shot}"
            # 这里需要实现Redis连接逻辑
            return None  # 占位符
        except Exception as e:
            print(f'获取数据URL失败: {e}')
            return None
    
    def _extract_labels_from_annotation(self, annotation: Dict) -> Dict:
        """从标注中提取标签"""
        labels = {}
        
        for result in annotation.get('result', []):
            label_group = result.get('from_name')
            if label_group == 'speed_level':
                labels['speed'] = result.get('value', {}).get('timeserieslabels', [''])[0]
            elif label_group == 'fault_type':
                labels['fault'] = result.get('value', {}).get('timeserieslabels', [''])[0]
            elif label_group == 'quality_score':
                labels['quality'] = result.get('value', {}).get('number', 0)
                
        return labels
    
    def _update_model_parameters(self, features: List[Dict], labels: List[Dict]):
        """更新模型参数"""
        # 实现模型参数更新逻辑
        # 这里可以集成scikit-learn或其他ML框架进行在线学习
        pass
