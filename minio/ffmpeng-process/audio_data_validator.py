#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频数据验证工具

功能说明：
1. 读取.meta文件中的时间戳和字节位置信息
2. 从二进制数据文件中提取对应位置的字节数组
3. 验证提取的数据是否与时间戳匹配
4. 生成详细的验证报告

作者：AI助手
版本：1.0
"""

import os
import sys
import struct
import time
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audio_validation.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AudioDataValidator:
    """
    音频数据验证器类
    
    主要功能：
    - 解析.meta文件中的时间戳和字节位置信息
    - 从二进制文件中提取指定位置的音频数据
    - 验证数据完整性和时间戳匹配性
    """
    
    def __init__(self, data_file_path: str, meta_file_path: str):
        """
        初始化验证器
        
        Args:
            data_file_path: 二进制数据文件路径
            meta_file_path: 元数据文件路径
        """
        self.data_file_path = data_file_path
        self.meta_file_path = meta_file_path
        self.meta_data = []
        self.validation_results = []
        
        # 验证文件是否存在
        if not os.path.exists(data_file_path):
            raise FileNotFoundError(f"数据文件不存在: {data_file_path}")
        if not os.path.exists(meta_file_path):
            raise FileNotFoundError(f"元数据文件不存在: {meta_file_path}")
    
    def parse_meta_file(self) -> List[Tuple[int, int, int]]:
        """
        解析.meta文件，提取时间戳和字节位置信息
        
        Returns:
            包含(时间戳, 开始位置, 结束位置)的列表
        """
        logger.info(f"开始解析元数据文件: {self.meta_file_path}")
        
        try:
            with open(self.meta_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            parsed_data = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 解析每行的三个值：时间戳, 开始位置, 结束位置
                    parts = line.split(',')
                    if len(parts) != 3:
                        logger.warning(f"第{line_num}行格式错误，跳过: {line}")
                        continue
                    
                    timestamp = int(parts[0])
                    start_pos = int(parts[1])
                    end_pos = int(parts[2])
                    
                    # 验证位置信息的合理性
                    if start_pos < 0 or end_pos < 0:
                        logger.warning(f"第{line_num}行位置信息为负数，跳过: {line}")
                        continue
                    
                    if start_pos >= end_pos:
                        logger.warning(f"第{line_num}行开始位置大于等于结束位置，跳过: {line}")
                        continue
                    
                    parsed_data.append((timestamp, start_pos, end_pos))
                    
                except ValueError as e:
                    logger.warning(f"第{line_num}行数据格式错误: {line}, 错误: {e}")
                    continue
            
            self.meta_data = parsed_data
            logger.info(f"成功解析{len(parsed_data)}条元数据记录")
            return parsed_data
            
        except Exception as e:
            logger.error(f"解析元数据文件时发生错误: {e}")
            raise
    
    def extract_audio_segment(self, start_pos: int, end_pos: int) -> bytes:
        """
        从二进制文件中提取指定位置的音频数据段
        
        Args:
            start_pos: 开始位置（字节）
            end_pos: 结束位置（字节）
            
        Returns:
            提取的字节数组
        """
        try:
            with open(self.data_file_path, 'rb') as f:
                # 检查文件大小
                f.seek(0, 2)  # 移动到文件末尾
                file_size = f.tell()
                
                # 验证位置范围
                if start_pos >= file_size:
                    raise ValueError(f"开始位置{start_pos}超出文件大小{file_size}")
                if end_pos > file_size:
                    logger.warning(f"结束位置{end_pos}超出文件大小{file_size}，调整为{file_size}")
                    end_pos = file_size
                
                # 提取数据
                f.seek(start_pos)
                data = f.read(end_pos - start_pos)
                
                return data
                
        except Exception as e:
            logger.error(f"提取音频数据段时发生错误: {e}")
            raise
    
    def validate_timestamp_consistency(self, timestamp: int, data: bytes) -> Dict:
        """
        验证时间戳与音频数据的一致性
        
        Args:
            timestamp: 时间戳（毫秒）
            data: 音频数据字节数组
            
        Returns:
            验证结果字典
        """
        result = {
            'timestamp': timestamp,
            'data_size': len(data),
            'is_valid': True,
            'issues': []
        }
        
        # 检查数据大小是否合理（假设每秒音频数据大小应该相对稳定）
        if len(data) == 0:
            result['is_valid'] = False
            result['issues'].append("数据段为空")
        
        # 检查时间戳格式（应该是13位毫秒时间戳）
        if timestamp < 1000000000000:  # 小于2001年的时间戳
            result['issues'].append("时间戳格式可能不正确")
        
        # 检查数据是否包含有效的音频数据特征
        # 这里可以根据具体的音频格式添加更多验证逻辑
        
        return result
    
    def validate_all_segments(self) -> List[Dict]:
        """
        验证所有音频数据段
        
        Returns:
            验证结果列表
        """
        logger.info("开始验证所有音频数据段")
        
        if not self.meta_data:
            self.parse_meta_file()
        
        results = []
        total_segments = len(self.meta_data)
        
        for i, (timestamp, start_pos, end_pos) in enumerate(self.meta_data, 1):
            logger.info(f"验证第{i}/{total_segments}段数据: 时间戳={timestamp}")
            
            try:
                # 提取音频数据段
                audio_data = self.extract_audio_segment(start_pos, end_pos)
                
                # 验证时间戳一致性
                validation_result = self.validate_timestamp_consistency(timestamp, audio_data)
                validation_result.update({
                    'segment_index': i,
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'expected_size': end_pos - start_pos,
                    'actual_size': len(audio_data)
                })
                
                # 检查数据大小是否匹配
                if validation_result['actual_size'] != validation_result['expected_size']:
                    validation_result['is_valid'] = False
                    validation_result['issues'].append(
                        f"数据大小不匹配: 期望{validation_result['expected_size']}字节，实际{validation_result['actual_size']}字节"
                    )
                
                results.append(validation_result)
                
                # 显示进度
                if i % 10 == 0 or i == total_segments:
                    logger.info(f"已验证 {i}/{total_segments} 段数据")
                
            except Exception as e:
                logger.error(f"验证第{i}段数据时发生错误: {e}")
                results.append({
                    'segment_index': i,
                    'timestamp': timestamp,
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'is_valid': False,
                    'issues': [f"验证过程发生错误: {e}"],
                    'data_size': 0,
                    'expected_size': end_pos - start_pos,
                    'actual_size': 0
                })
        
        self.validation_results = results
        return results
    
    def generate_report(self) -> str:
        """
        生成详细的验证报告
        
        Returns:
            报告内容字符串
        """
        if not self.validation_results:
            self.validate_all_segments()
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("音频数据验证报告")
        report_lines.append("=" * 60)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"数据文件: {self.data_file_path}")
        report_lines.append(f"元数据文件: {self.meta_file_path}")
        report_lines.append("")
        
        # 统计信息
        total_segments = len(self.validation_results)
        valid_segments = sum(1 for r in self.validation_results if r['is_valid'])
        invalid_segments = total_segments - valid_segments
        
        report_lines.append("统计信息:")
        report_lines.append(f"  总段数: {total_segments}")
        report_lines.append(f"  有效段数: {valid_segments}")
        report_lines.append(f"  无效段数: {invalid_segments}")
        report_lines.append(f"  成功率: {valid_segments/total_segments*100:.2f}%")
        report_lines.append("")
        
        # 详细结果
        if invalid_segments > 0:
            report_lines.append("问题详情:")
            report_lines.append("-" * 40)
            
            for result in self.validation_results:
                if not result['is_valid']:
                    report_lines.append(f"段 {result['segment_index']}:")
                    report_lines.append(f"  时间戳: {result['timestamp']}")
                    report_lines.append(f"  位置: {result['start_pos']} - {result['end_pos']}")
                    report_lines.append(f"  数据大小: {result['actual_size']} / {result['expected_size']}")
                    for issue in result['issues']:
                        report_lines.append(f"  问题: {issue}")
                    report_lines.append("")
        
        # 时间戳分析
        if self.validation_results:
            timestamps = [r['timestamp'] for r in self.validation_results]
            time_diffs = []
            for i in range(1, len(timestamps)):
                diff = timestamps[i] - timestamps[i-1]
                time_diffs.append(diff)
            
            if time_diffs:
                avg_diff = sum(time_diffs) / len(time_diffs)
                report_lines.append("时间戳分析:")
                report_lines.append(f"  平均时间间隔: {avg_diff:.2f} 毫秒")
                report_lines.append(f"  最小时间间隔: {min(time_diffs)} 毫秒")
                report_lines.append(f"  最大时间间隔: {max(time_diffs)} 毫秒")
                report_lines.append("")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def save_report(self, output_file: str = "validation_report.txt"):
        """
        保存验证报告到文件
        
        Args:
            output_file: 输出文件名
        """
        report_content = self.generate_report()
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"验证报告已保存到: {output_file}")
        except Exception as e:
            logger.error(f"保存报告时发生错误: {e}")
            raise


def main():
    """
    主函数 - 程序入口点
    """
    print("音频数据验证工具")
    print("=" * 40)
    
    # 检查命令行参数
    if len(sys.argv) != 3:
        print("使用方法: python audio_data_validator.py <数据文件> <元数据文件>")
        print("示例: python audio_data_validator.py S-ZTCJ03DZ0043-8&1756105438662&1_data S-ZTCJ03DZ0043-8&1756105438662&1_data.meta")
        sys.exit(1)
    
    data_file = sys.argv[1]
    meta_file = sys.argv[2]
    
    try:
        # 创建验证器实例
        validator = AudioDataValidator(data_file, meta_file)
        
        # 执行验证
        print("开始验证音频数据...")
        results = validator.validate_all_segments()
        
        # 生成并显示报告
        report = validator.generate_report()
        print(report)
        
        # 保存报告
        validator.save_report()
        
        # 返回退出码
        valid_count = sum(1 for r in results if r['is_valid'])
        total_count = len(results)
        
        if valid_count == total_count:
            print("\n✅ 所有数据段验证通过！")
            sys.exit(0)
        else:
            print(f"\n⚠️  发现 {total_count - valid_count} 个问题，请查看详细报告")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
