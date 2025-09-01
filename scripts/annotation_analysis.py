import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
import json
import toklabel
from vibration_data_manager import VibrationDataManager

class VibrationAnnotationAnalyzer:
    """振动数据标注分析器 - 生成标注报告和可视化图表"""
    
    def __init__(self, postgres_config: Dict, redis_config: Dict):
        self.data_manager = VibrationDataManager(postgres_config, redis_config)
        
    def export_annotation_report(self, shots: List[int], output_path: str):
        """导出标注报告"""
        
        # 查询所有标注数据
        annotations = self.data_manager.query_annotations_by_conditions(shot_ids=shots)
        
        if not annotations:
            print('没有找到标注数据')
            return
        
        # 转换为DataFrame进行分析
        df = pd.DataFrame(annotations)
        
        # 生成统计报告
        report = {
            'summary': {
                'total_annotations': len(df),
                'unique_shots': df['shot_id'].nunique(),
                'label_groups': df['label_group'].unique().tolist(),
                'date_range': {
                    'start': df['created_at'].min().isoformat() if 'created_at' in df.columns else None,
                    'end': df['created_at'].max().isoformat() if 'created_at' in df.columns else None
                }
            },
            'label_distribution': {},
            'quality_analysis': {},
            'confidence_analysis': {},
            'fault_analysis': {}
        }
        
        # 标签分布统计
        for label_group in df['label_group'].unique():
            group_df = df[df['label_group'] == label_group]
            if label_group == 'quality_score':
                report['label_distribution'][label_group] = {
                    'count': len(group_df),
                    'mean': float(group_df['number_value'].mean()),
                    'std': float(group_df['number_value'].std()),
                    'min': float(group_df['number_value'].min()),
                    'max': float(group_df['number_value'].max())
                }
            else:
                label_counts = group_df['label_value'].value_counts().to_dict()
                report['label_distribution'][label_group] = label_counts
        
        # 质量分析
        quality_stats = self._get_quality_statistics(shots)
        report['quality_analysis'] = quality_stats
        
        # 置信度分析
        confidence_stats = {
            'mean_confidence': float(df['confidence'].mean()),
            'std_confidence': float(df['confidence'].std()),
            'low_confidence_count': len(df[df['confidence'] < 0.7]),
            'high_confidence_count': len(df[df['confidence'] >= 0.9])
        }
        report['confidence_analysis'] = confidence_stats
        
        # 故障分析
        fault_df = df[df['label_group'] == 'fault_type']
        if not fault_df.empty:
            fault_distribution = fault_df['label_value'].value_counts().to_dict()
            normal_ratio = fault_distribution.get('正常', 0) / len(fault_df)
            report['fault_analysis'] = {
                'fault_distribution': fault_distribution,
                'normal_ratio': float(normal_ratio),
                'fault_ratio': float(1 - normal_ratio)
            }
        
        # 保存报告
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        print(f'标注报告导出完成: {output_path}')
        return report
    
    def generate_comprehensive_charts(self, shots: List[int], output_dir: str):
        """生成综合分析图表"""
        annotations = self.data_manager.query_annotations_by_conditions(shot_ids=shots)
        
        if not annotations:
            print('没有标注数据')
            return
        
        df = pd.DataFrame(annotations)
        
        # 1. 质量趋势图
        quality_df = df[df['label_group'] == 'quality_score']
        if not quality_df.empty:
            plt.figure(figsize=(12, 6))
            plt.plot(quality_df['shot_id'], quality_df['number_value'], 'o-', linewidth=2, markersize=6)
            plt.xlabel('设备编号')
            plt.ylabel('质量分数')
            plt.title('设备健康质量趋势')
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f'{output_dir}/quality_trend.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 2. 故障类型分布饼图
        fault_df = df[df['label_group'] == 'fault_type']
        if not fault_df.empty:
            fault_counts = fault_df['label_value'].value_counts()
            plt.figure(figsize=(8, 8))
            plt.pie(fault_counts.values, labels=fault_counts.index, autopct='%1.1f%%')
            plt.title('故障类型分布')
            plt.savefig(f'{output_dir}/fault_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 3. 置信度分布直方图
        plt.figure(figsize=(10, 6))
        plt.hist(df['confidence'], bins=20, alpha=0.7, edgecolor='black')
        plt.xlabel('置信度')
        plt.ylabel('频次')
        plt.title('预测置信度分布')
        plt.grid(True, alpha=0.3)
        plt.savefig(f'{output_dir}/confidence_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. 转速段分布柱状图
        speed_df = df[df['label_group'] == 'speed_level']
        if not speed_df.empty:
            speed_counts = speed_df['label_value'].value_counts()
            plt.figure(figsize=(10, 6))
            speed_counts.plot(kind='bar')
            plt.xlabel('转速段')
            plt.ylabel('设备数量')
            plt.title('转速段分布')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f'{output_dir}/speed_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f'图表生成完成，保存在: {output_dir}')
    
    def _get_quality_statistics(self, shots: List[int]) -> Dict:
        """获取质量分数统计信息"""
        annotations = self.data_manager.query_annotations_by_conditions(
            shot_ids=shots,
            label_groups=['quality_score']
        )
        
        quality_scores = [anno['number_value'] for anno in annotations 
                         if anno['number_value'] is not None]
        
        if not quality_scores:
            return {}
        
        return {
            'mean_quality': float(np.mean(quality_scores)),
            'std_quality': float(np.std(quality_scores)),
            'min_quality': float(np.min(quality_scores)),
            'max_quality': float(np.max(quality_scores)),
            'count': len(quality_scores)
        }
    
    def export_training_data_for_ml(self, shots: List[int], output_path: str):
        """导出用于机器学习的训练数据"""
        training_data = self.data_manager.export_training_dataset(output_path, shots)
        return training_data

def main():
    """主函数 - 运行标注分析"""
    POSTGRES_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'vibration_phm',
        'user': 'postgres',
        'password': 'password'
    }
    
    REDIS_CONFIG = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }
    
    # 创建分析器
    analyzer = VibrationAnnotationAnalyzer(POSTGRES_CONFIG, REDIS_CONFIG)
    
    # 分析设备240829001-240829010的标注数据
    shots = list(range(240829001, 240829011))
    
    # 生成标注报告
    report = analyzer.export_annotation_report(shots, 'vibration_annotation_report.json')
    
    # 生成图表
    analyzer.generate_comprehensive_charts(shots, 'charts')
    
    # 导出训练数据
    analyzer.export_training_data_for_ml(shots, 'training_data.json')
    
    print('标注分析完成！')

if __name__ == "__main__":
    main()
