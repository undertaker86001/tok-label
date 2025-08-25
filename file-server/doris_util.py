import pandas as pd
import pymysql
import pymysql.cursors
from typing import Dict, List, Tuple, Optional, Union
import numpy as np
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Doris 配置
DORIS_FE_HOST = os.getenv('DORIS_FE_HOST', 'localhost')
DORIS_FE_PORT = int(os.getenv('DORIS_FE_PORT', '9030'))
DORIS_USER = os.getenv('DORIS_USER', 'root')
DORIS_PASSWORD = os.getenv('DORIS_PASSWORD', '')
DORIS_DATABASE = os.getenv('DORIS_DATABASE', 'test_db')

def connect_to_doris_database():
    """
    连接到 Doris 数据库
    
    返回:
    ----
    pymysql.Connection: Doris 数据库连接对象
    """
    try:
        conn = pymysql.connect(
            host=DORIS_FE_HOST,
            port=DORIS_FE_PORT,
            user=DORIS_USER,
            password=DORIS_PASSWORD,
            database=DORIS_DATABASE,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return conn
    except Exception as e:
        print(f"连接 Doris 数据库失败: {e}")
        raise

def close_doris_connection(conn):
    """
    关闭 Doris 数据库连接
    
    参数:
    ----
    conn: pymysql.Connection
        数据库连接对象
    """
    if conn:
        conn.close()

def load_doris_data(
    conn,
    shot: Union[int, str],
    name_table_columns: Dict[str, Tuple[str, List[str]]],
    t_min: float = -np.inf,
    t_max: float = np.inf,
    resolution: float = 1e-3
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    从 Doris 数据库加载指定炮号的数据
    
    参数:
    ----
    conn: pymysql.Connection
        Doris 数据库连接
    shot: int 或 str
        炮号
    name_table_columns: Dict[str, Tuple[str, List[str]]]
        表和列的映射关系
    t_min: float
        最小时间
    t_max: float
        最大时间
    resolution: float
        时间分辨率
    
    返回:
    ----
    Tuple[np.ndarray, Dict[str, np.ndarray]]: 时间数组和数据字典
    """
    data_dict = {}
    time_array = None
    
    with conn.cursor() as cursor:
        for name, (table_name, columns) in name_table_columns.items():
            try:
                # 构建列名字符串
                if isinstance(columns, list):
                    if len(columns) == 1:
                        col_str = f"`{columns[0]}`"
                    else:
                        col_str = ", ".join([f"`{col}`" for col in columns])
                else:
                    col_str = f"`{columns}`"
                
                # 构建查询 SQL - 适配 Doris 语法
                base_sql = f"""
                    SELECT `time`, {col_str}
                    FROM `{table_name}`
                    WHERE `shot` = %s
                """
                
                # 添加时间范围条件
                conditions = []
                params = [shot]
                
                if t_min != -np.inf:
                    conditions.append("`time` >= %s")
                    params.append(t_min)
                
                if t_max != np.inf:
                    conditions.append("`time` <= %s")
                    params.append(t_max)
                
                if conditions:
                    base_sql += " AND " + " AND ".join(conditions)
                
                # 添加排序
                base_sql += " ORDER BY `time`"
                
                # 执行查询
                cursor.execute(base_sql, params)
                rows = cursor.fetchall()
                
                if not rows:
                    print(f"警告: 表 {table_name} 中没有找到炮号 {shot} 的数据")
                    continue
                
                # 提取时间和数据
                times = np.array([row['time'] for row in rows])
                
                if isinstance(columns, list) and len(columns) > 1:
                    # 多列数据
                    data_values = []
                    for col in columns:
                        col_data = [row[col] for row in rows]
                        data_values.append(col_data)
                    data_array = np.array(data_values)  # shape: (n_cols, n_times)
                else:
                    # 单列数据
                    col_name = columns[0] if isinstance(columns, list) else columns
                    col_data = [row[col_name] for row in rows]
                    data_array = np.array([col_data])  # shape: (1, n_times)
                
                # 时间降采样处理
                if resolution > 0:
                    # 创建均匀时间网格
                    t_start = max(times.min(), t_min if t_min != -np.inf else times.min())
                    t_end = min(times.max(), t_max if t_max != np.inf else times.max())
                    
                    if t_end > t_start:
                        n_points = int((t_end - t_start) / resolution) + 1
                        uniform_times = np.linspace(t_start, t_end, n_points)
                        
                        # 对每列数据进行插值
                        interpolated_data = []
                        for i in range(data_array.shape[0]):
                            interp_values = np.interp(uniform_times, times, data_array[i])
                            interpolated_data.append(interp_values)
                        
                        times = uniform_times
                        data_array = np.array(interpolated_data)
                
                # 存储结果
                data_dict[name] = data_array
                
                # 使用第一个表的时间作为基准时间
                if time_array is None:
                    time_array = times
                    
            except Exception as e:
                print(f"查询表 {table_name} 时出错: {e}")
                continue
    
    if time_array is None:
        time_array = np.array([])
    
    return time_array, data_dict

def export_doris_data(
    shots: Union[int, List[int]], 
    name_table_columns: Dict[str, Tuple[str, List[str]]], 
    t_min: float = -np.inf, 
    t_max: float = np.inf, 
    resolution: float = 1e-3
) -> Dict[Union[int, str], pd.DataFrame]:
    """
    从 Doris 中读取指定炮号的数据，并将其转换为 DataFrame 格式
    
    参数:
    ----
    shots: int, str 或 List
        炮号或炮号列表
    name_table_columns: Dict[str, Tuple[str, List[str]]]
        表和列的映射关系，格式:
        {
            "some_name": ("table_name", ["col1", "col2", ...]),
            "other_name": ("other_table", ["colA", "colB", ...])
        }
    t_min: float
        数据的最小时间
    t_max: float  
        数据的最大时间
    resolution: float
        数据降采样分辨率(秒)
    
    返回:
    ----
    Dict[Union[int, str], pd.DataFrame]
        返回一个字典，每个键为炮号，每个值为该炮号对应的数据DataFrame
    """
    pd_data_dict = {}
    conn = connect_to_doris_database()
    
    try:
        # 将 shots 包装为列表
        if isinstance(shots, (str, int)):
            shots = [shots]
        elif hasattr(shots, '__iter__'):
            shots = list(shots)
        else:
            shots = [shots]
        
        # 针对每个 shot 处理数据
        for shot in shots:
            try:
                t, data_dict = load_doris_data(
                    conn,
                    shot=shot,
                    name_table_columns=name_table_columns,
                    t_min=t_min,
                    t_max=t_max,
                    resolution=resolution
                )
                
                if len(t) == 0:
                    print(f"警告: 炮号 {shot} 没有数据")
                    continue
                
                # 建立一个初始 DataFrame，将时间 t 设为第一列
                df_all = pd.DataFrame({"time": t})
                
                # 循环每个 key，将其数据合并到 df_all
                for name, array_data in data_dict.items():
                    # array_data.shape = (n_cols, len(t))，转置后成为 (len(t), n_cols)
                    array_data_T = array_data.T
                    
                    # 获取对应的列名
                    _, col_names = name_table_columns[name]
                    if name == 'view_data':
                        df_temp = pd.DataFrame(array_data_T, columns=[f"{col}" for col in col_names])
                    else:    
                        df_temp = pd.DataFrame(array_data_T, columns=[f"{name}_{col}" for col in col_names])
                    
                    # 拼接临时表与主表（按列）
                    df_all = pd.concat([df_all, df_temp], axis=1)
                
                # 以 shot 作为 key 标记当前数据
                pd_data_dict[shot] = df_all
                
            except Exception as e:
                print(f"处理炮号 {shot} 时出错: {e}")
                continue
                
    finally:
        # 关闭数据库连接
        close_doris_connection(conn)
    
    return pd_data_dict
