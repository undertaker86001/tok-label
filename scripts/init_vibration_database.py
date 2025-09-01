import psycopg2
from typing import Dict
import numpy as np

def create_vibration_tables(postgres_config: Dict):
    """创建振动数据相关表"""
    
    with psycopg2.connect(**postgres_config) as conn:
        cursor = conn.cursor()
        
        # 创建振动传感器数据表
        vibration_sensors_sql = """
        CREATE TABLE IF NOT EXISTS vibration_sensors (
            id SERIAL PRIMARY KEY,
            shot_id INTEGER NOT NULL,
            time_stamp FLOAT NOT NULL,
            x_axis FLOAT,
            y_axis FLOAT,
            z_axis FLOAT,
            sensor_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_vibration_shot_time 
        ON vibration_sensors(shot_id, time_stamp);
        """
        
        # 创建转速传感器数据表
        rotation_sensors_sql = """
        CREATE TABLE IF NOT EXISTS rotation_sensors (
            id SERIAL PRIMARY KEY,
            shot_id INTEGER NOT NULL,
            time_stamp FLOAT NOT NULL,
            rpm FLOAT,
            sensor_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_rotation_shot_time 
        ON rotation_sensors(shot_id, time_stamp);
        """
        
        # 创建设备信息表
        equipment_info_sql = """
        CREATE TABLE IF NOT EXISTS equipment_info (
            shot_id INTEGER PRIMARY KEY,
            equipment_name VARCHAR(100),
            equipment_type VARCHAR(50),
            location VARCHAR(100),
            installation_date DATE,
            last_maintenance DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # 执行建表语句
        cursor.execute(vibration_sensors_sql)
        cursor.execute(rotation_sensors_sql)
        cursor.execute(equipment_info_sql)
        
        conn.commit()
        print('振动数据表创建成功')

def insert_sample_data(postgres_config: Dict):
    """插入示例振动数据"""
    
    with psycopg2.connect(**postgres_config) as conn:
        cursor = conn.cursor()
        
        # 生成示例振动数据
        import numpy as np
        
        for shot_id in range(240829001, 240829011):  # 10个设备
            print(f'生成设备 {shot_id} 示例数据...')
            
            # 生成60秒的振动数据，1ms分辨率
            time_points = np.arange(0, 60, 0.001)
            
            # 模拟振动信号
            base_freq = np.random.uniform(10, 50)  # 基础频率
            noise_level = np.random.uniform(0.1, 0.5)
            
            vibration_x = np.sin(2 * np.pi * base_freq * time_points) + \
                         noise_level * np.random.normal(0, 1, len(time_points))
            vibration_y = np.cos(2 * np.pi * base_freq * time_points) + \
                         noise_level * np.random.normal(0, 1, len(time_points))
            vibration_z = 0.5 * np.sin(2 * np.pi * base_freq * 2 * time_points) + \
                         noise_level * np.random.normal(0, 1, len(time_points))
            
            # 模拟转速变化
            base_rpm = np.random.uniform(500, 2000)
            rpm_variation = 100 * np.sin(2 * np.pi * 0.1 * time_points)  # 缓慢变化
            rotation_speed = base_rpm + rpm_variation + \
                           10 * np.random.normal(0, 1, len(time_points))
            
            # 批量插入振动数据（每100个点一批）
            batch_size = 100
            for i in range(0, len(time_points), batch_size):
                end_idx = min(i + batch_size, len(time_points))
                
                vibration_batch = [
                    (shot_id, time_points[j], vibration_x[j], vibration_y[j], vibration_z[j], 'sensor_001')
                    for j in range(i, end_idx)
                ]
                
                rotation_batch = [
                    (shot_id, time_points[j], rotation_speed[j], 'rpm_sensor_001')
                    for j in range(i, end_idx)
                ]
                
                # 插入振动数据
                cursor.executemany(
                    "INSERT INTO vibration_sensors (shot_id, time_stamp, x_axis, y_axis, z_axis, sensor_id) VALUES (%s, %s, %s, %s, %s, %s)",
                    vibration_batch
                )
                
                # 插入转速数据
                cursor.executemany(
                    "INSERT INTO rotation_sensors (shot_id, time_stamp, rpm, sensor_id) VALUES (%s, %s, %s, %s)",
                    rotation_batch
                )
            
            # 插入设备信息
            cursor.execute(
                "INSERT INTO equipment_info (shot_id, equipment_name, equipment_type, location) VALUES (%s, %s, %s, %s)",
                (shot_id, f'设备_{shot_id}', '离心泵', f'车间A-{shot_id % 10}')
            )
            
            conn.commit()
        
        print('示例数据插入完成')

if __name__ == "__main__":
    POSTGRES_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'vibration_phm',
        'user': 'postgres',
        'password': 'password'
    }
    
    create_vibration_tables(POSTGRES_CONFIG)
    insert_sample_data(POSTGRES_CONFIG)
