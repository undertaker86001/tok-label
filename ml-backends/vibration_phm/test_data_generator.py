"""
振动数据测试数据生成器

用于生成各种测试场景的振动数据，包括：
- 正常振动数据
- 故障振动数据
- 边界情况数据
- 性能测试数据
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import json
import os


class VibrationTestDataGenerator:
    """振动数据测试数据生成器"""
    
    def __init__(self, sample_rate: float = 1000.0):
        """
        初始化数据生成器
        
        Args:
            sample_rate: 采样率，默认1000Hz
        """
        self.sample_rate = sample_rate
        self.time_step = 1.0 / sample_rate
    
    def generate_normal_vibration_data(self, duration: float = 60.0, shot_id: int = 240829001) -> pd.DataFrame:
        """
        生成正常振动数据
        
        Args:
            duration: 数据持续时间（秒）
            shot_id: 设备ID
            
        Returns:
            正常振动数据DataFrame
        """
        time_points = np.arange(0, duration, self.time_step)
        
        # 基础频率（设备正常运行频率）
        base_freq = 30.0  # 30Hz
        noise_level = 0.1
        
        # 生成三轴振动数据
        vibration_x = np.sin(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_y = np.cos(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        
        # 生成转速数据（中转速范围）
        base_rpm = 1200.0
        rpm_variation = 20.0 * np.sin(2 * np.pi * 0.02 * time_points)  # 缓慢变化
        rotation_speed = base_rpm + rpm_variation + \
                        2.0 * np.random.normal(0, 1, len(time_points))
        
        # 计算振动幅值
        vibration_amplitude = np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
        
        return pd.DataFrame({
            'time': time_points,
            'vibration_x': vibration_x,
            'vibration_y': vibration_y,
            'vibration_z': vibration_z,
            'rotation_speed': rotation_speed,
            'vibration_amplitude': vibration_amplitude,
            'shot_id': shot_id
        })
    
    def generate_unbalance_vibration_data(self, duration: float = 60.0, shot_id: int = 240829002) -> pd.DataFrame:
        """
        生成不平衡故障振动数据
        
        Args:
            duration: 数据持续时间（秒）
            shot_id: 设备ID
            
        Returns:
            不平衡故障振动数据DataFrame
        """
        time_points = np.arange(0, duration, self.time_step)
        
        # 基础频率
        base_freq = 30.0
        noise_level = 0.15
        
        # 不平衡故障特征：增加一倍频成分
        unbalance_amplitude = 2.0
        vibration_x = np.sin(2 * np.pi * base_freq * time_points) + \
                     unbalance_amplitude * np.sin(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_y = np.cos(2 * np.pi * base_freq * time_points) + \
                     unbalance_amplitude * np.cos(2 * np.pi * base_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        
        # 转速数据
        base_rpm = 1200.0
        rotation_speed = base_rpm + 5.0 * np.random.normal(0, 1, len(time_points))
        
        vibration_amplitude = np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
        
        return pd.DataFrame({
            'time': time_points,
            'vibration_x': vibration_x,
            'vibration_y': vibration_y,
            'vibration_z': vibration_z,
            'rotation_speed': rotation_speed,
            'vibration_amplitude': vibration_amplitude,
            'shot_id': shot_id
        })
    
    def generate_bearing_fault_data(self, duration: float = 60.0, shot_id: int = 240829003) -> pd.DataFrame:
        """
        生成轴承故障振动数据
        
        Args:
            duration: 数据持续时间（秒）
            shot_id: 设备ID
            
        Returns:
            轴承故障振动数据DataFrame
        """
        time_points = np.arange(0, duration, self.time_step)
        
        # 基础频率
        base_freq = 30.0
        noise_level = 0.2
        
        # 轴承故障特征：增加高频成分和冲击
        bearing_freq = 150.0  # 轴承故障特征频率
        impact_interval = int(self.sample_rate * 0.1)  # 每0.1秒一次冲击
        
        vibration_x = np.sin(2 * np.pi * base_freq * time_points) + \
                     0.5 * np.sin(2 * np.pi * bearing_freq * time_points)
        vibration_y = np.cos(2 * np.pi * base_freq * time_points) + \
                     0.5 * np.cos(2 * np.pi * bearing_freq * time_points)
        vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points)
        
        # 添加冲击
        for i in range(0, len(time_points), impact_interval):
            if i < len(vibration_x):
                vibration_x[i] += 3.0 * np.exp(-(time_points[i] % 0.1) * 50)
                vibration_y[i] += 3.0 * np.exp(-(time_points[i] % 0.1) * 50)
        
        # 添加噪声
        vibration_x += noise_level * np.random.normal(0, 1, len(time_points))
        vibration_y += noise_level * np.random.normal(0, 1, len(time_points))
        vibration_z += noise_level * np.random.normal(0, 1, len(time_points))
        
        # 转速数据
        base_rpm = 1200.0
        rotation_speed = base_rpm + 3.0 * np.random.normal(0, 1, len(time_points))
        
        vibration_amplitude = np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
        
        return pd.DataFrame({
            'time': time_points,
            'vibration_x': vibration_x,
            'vibration_y': vibration_y,
            'vibration_z': vibration_z,
            'rotation_speed': rotation_speed,
            'vibration_amplitude': vibration_amplitude,
            'shot_id': shot_id
        })
    
    def generate_gear_fault_data(self, duration: float = 60.0, shot_id: int = 240829004) -> pd.DataFrame:
        """
        生成齿轮故障振动数据
        
        Args:
            duration: 数据持续时间（秒）
            shot_id: 设备ID
            
        Returns:
            齿轮故障振动数据DataFrame
        """
        time_points = np.arange(0, duration, self.time_step)
        
        # 基础频率
        base_freq = 30.0
        gear_freq = 90.0  # 齿轮啮合频率
        noise_level = 0.25
        
        # 齿轮故障特征：调制现象
        modulation_freq = 5.0  # 调制频率
        
        vibration_x = np.sin(2 * np.pi * base_freq * time_points) * \
                     (1 + 0.5 * np.sin(2 * np.pi * modulation_freq * time_points)) + \
                     0.8 * np.sin(2 * np.pi * gear_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_y = np.cos(2 * np.pi * base_freq * time_points) * \
                     (1 + 0.5 * np.cos(2 * np.pi * modulation_freq * time_points)) + \
                     0.8 * np.cos(2 * np.pi * gear_freq * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points) + \
                     noise_level * np.random.normal(0, 1, len(time_points))
        
        # 转速数据
        base_rpm = 1200.0
        rotation_speed = base_rpm + 4.0 * np.random.normal(0, 1, len(time_points))
        
        vibration_amplitude = np.sqrt(vibration_x**2 + vibration_y**2 + vibration_z**2)
        
        return pd.DataFrame({
            'time': time_points,
            'vibration_x': vibration_x,
            'vibration_y': vibration_y,
            'vibration_z': vibration_z,
            'rotation_speed': rotation_speed,
            'vibration_amplitude': vibration_amplitude,
            'shot_id': shot_id
        })
    
    def generate_edge_case_data(self, case: str = "empty", shot_id: int = 240829005) -> pd.DataFrame:
        """
        生成边界情况数据
        
        Args:
            case: 边界情况类型 ("empty", "partial", "nan", "extreme")
            shot_id: 设备ID
            
        Returns:
            边界情况数据DataFrame
        """
        if case == "empty":
            return pd.DataFrame()
        
        elif case == "partial":
            # 只有部分列的数据
            time_points = np.arange(0, 10, self.time_step)
            return pd.DataFrame({
                'time': time_points,
                'vibration_x': np.random.normal(0, 1, len(time_points))
            })
        
        elif case == "nan":
            # 包含NaN值的数据
            time_points = np.arange(0, 10, self.time_step)
            vibration_x = np.random.normal(0, 1, len(time_points))
            vibration_x[5:10] = np.nan  # 插入NaN值
            
            return pd.DataFrame({
                'time': time_points,
                'vibration_x': vibration_x,
                'vibration_y': np.random.normal(0, 1, len(time_points)),
                'vibration_z': np.random.normal(0, 1, len(time_points)),
                'rotation_speed': np.random.uniform(500, 2000, len(time_points))
            })
        
        elif case == "extreme":
            # 极值数据
            time_points = np.arange(0, 10, self.time_step)
            return pd.DataFrame({
                'time': time_points,
                'vibration_x': np.full(len(time_points), 1e6),  # 极大值
                'vibration_y': np.full(len(time_points), -1e6),  # 极小值
                'vibration_z': np.full(len(time_points), 0),
                'rotation_speed': np.full(len(time_points), 10000)  # 极高转速
            })
        
        else:
            raise ValueError(f"Unknown edge case: {case}")
    
    def generate_performance_test_data(self, num_shots: int = 10, duration: float = 60.0) -> Dict[int, pd.DataFrame]:
        """
        生成性能测试数据
        
        Args:
            num_shots: 设备数量
            duration: 每个设备的数据持续时间
            
        Returns:
            多个设备的振动数据字典
        """
        data_dict = {}
        
        for i in range(num_shots):
            shot_id = 240829010 + i
            data_dict[shot_id] = self.generate_normal_vibration_data(duration, shot_id)
        
        return data_dict
    
    def save_test_data_to_csv(self, data: pd.DataFrame, filename: str, output_dir: str = "test_data"):
        """
        保存测试数据到CSV文件
        
        Args:
            data: 振动数据DataFrame
            filename: 文件名
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        data.to_csv(filepath, index=False)
        print(f"测试数据已保存到: {filepath}")
    
    def generate_test_dataset(self, output_dir: str = "test_data"):
        """
        生成完整的测试数据集
        
        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成各种类型的测试数据
        test_cases = [
            ("normal_vibration.csv", self.generate_normal_vibration_data(60.0, 240829001)),
            ("unbalance_fault.csv", self.generate_unbalance_vibration_data(60.0, 240829002)),
            ("bearing_fault.csv", self.generate_bearing_fault_data(60.0, 240829003)),
            ("gear_fault.csv", self.generate_gear_fault_data(60.0, 240829004)),
            ("partial_data.csv", self.generate_edge_case_data("partial", 240829005)),
            ("nan_data.csv", self.generate_edge_case_data("nan", 240829006)),
            ("extreme_data.csv", self.generate_edge_case_data("extreme", 240829007))
        ]
        
        # 保存测试数据
        for filename, data in test_cases:
            self.save_test_data_to_csv(data, filename, output_dir)
        
        # 生成性能测试数据
        performance_data = self.generate_performance_test_data(5, 30.0)
        for shot_id, data in performance_data.items():
            filename = f"performance_test_{shot_id}.csv"
            self.save_test_data_to_csv(data, filename, output_dir)
        
        print(f"测试数据集生成完成，共{len(test_cases) + len(performance_data)}个文件")


def main():
    """主函数 - 生成测试数据集"""
    generator = VibrationTestDataGenerator()
    generator.generate_test_dataset()
    
    print("=== 测试数据生成完成 ===")
    print("生成的数据文件包括：")
    print("- normal_vibration.csv: 正常振动数据")
    print("- unbalance_fault.csv: 不平衡故障数据")
    print("- bearing_fault.csv: 轴承故障数据")
    print("- gear_fault.csv: 齿轮故障数据")
    print("- partial_data.csv: 部分数据")
    print("- nan_data.csv: 包含NaN的数据")
    print("- extreme_data.csv: 极值数据")
    print("- performance_test_*.csv: 性能测试数据")


if __name__ == "__main__":
    main()
