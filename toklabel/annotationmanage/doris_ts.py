import pymysql
from pymysql.connections import Connection
from typing import Optional, Dict, Any, List, Sequence
from datetime import datetime
from .doris_utils import (
    connect_doris_database, get_table_columns, 
    string_to_datetime, execute_batch_insert
)
from ..config import DORIS_DATABASE

def create_annotation_table(
    doris_conn: Connection,
    table_name: str,
    multi_label_group: bool = False,
    with_label: bool = True,
    label_name: str = None,
    unique_shot: bool = False,
    point_allowed: bool = True
):
    """
    在 Doris 中创建标注表
    
    参数:
    ----
    doris_conn: Doris 连接对象
    table_name: 表名
    multi_label_group: 是否涉及多个标签组
    with_label: 是否包含 label 字段
    label_name: label 列的名称
    unique_shot: 是否为 shot 加唯一约束
    point_allowed: 是否允许存储 is_point
    """
    # 构造列定义
    cols = [
        "id BIGINT AUTO_INCREMENT",
        "shot INT NOT NULL",
    ]
    
    if multi_label_group:
        cols.append('feature VARCHAR(50)')
        cols.append('label VARCHAR(50)')
    elif with_label:
        if label_name is None:
            label_name = 'label'
        cols.append(f"`{label_name}` VARCHAR(50)")
    
    cols.extend([
        "start_time DOUBLE",
        "end_time DOUBLE"
    ])
    
    if point_allowed:
        cols.append("is_point BOOLEAN DEFAULT FALSE")
    
    cols.extend([
        "annotator INT",
        "annotation_id INT",
        "annotation_created DATETIME DEFAULT CURRENT_TIMESTAMP",
        "annotation_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    ])
    
    # 构造建表语句
    col_def = ",\n    ".join(cols)
    
    # 根据是否需要唯一约束选择表模型
    if unique_shot:
        # 使用 UNIQUE KEY 模型
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            {col_def}
        ) UNIQUE KEY(shot)
        DISTRIBUTED BY HASH(shot) BUCKETS 10
        PROPERTIES (
            "replication_allocation" = "tag.location.default: 1"
        )
        """
    else:
        # 使用 DUPLICATE KEY 模型
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            {col_def}
        ) DUPLICATE KEY(id, shot)
        DISTRIBUTED BY HASH(shot) BUCKETS 10
        PROPERTIES (
            "replication_allocation" = "tag.location.default: 1"
        )
        """
    
    with doris_conn.cursor() as cursor:
        cursor.execute(create_sql)
        doris_conn.commit()

def insert_annotations(
    doris_conn: Connection,
    table_name: str,
    data_list: List[Dict[str, Any]],
    on_conflict: Optional[str] = None
):
    """
    插入标注数据到 Doris
    
    参数:
    ----
    doris_conn: Doris 连接对象
    table_name: 表名
    data_list: 数据列表
    on_conflict: 冲突处理策略（Doris 中通过 UNIQUE KEY 模型处理）
    """
    if not data_list:
        return
    
    # 获取所有键
    all_keys = set()
    for d in data_list:
        all_keys.update(d.keys())
    
    # 验证必需字段
    required_fields = {"shot", "start_time", "end_time"}
    if not required_fields.issubset(all_keys):
        raise ValueError(f"Each annotation must have at least {required_fields}")
    
    # 检查表列
    table_columns = set(get_table_columns(doris_conn, table_name))
    if not all_keys.issubset(table_columns):
        print(f'表列: {table_columns}')
        print(f'数据键: {all_keys}')
        raise ValueError("Data keys don't match table columns")
    
    col_list = sorted(all_keys)
    
    # 构造插入语句
    col_str = ", ".join(f"`{col}`" for col in col_list)
    placeholders = ", ".join(["%s"] * len(col_list))
    
    insert_sql = f"INSERT INTO `{table_name}` ({col_str}) VALUES ({placeholders})"
    
    # 准备数据
    rows_data = []
    for d in data_list:
        row = []
        for col in col_list:
            value = d.get(col, None)
            # 处理时间字段
            if col in ['annotation_created', 'annotation_updated'] and isinstance(value, str):
                value = string_to_datetime(value)
            row.append(value)
        rows_data.append(tuple(row))
    
    # 批量插入
    execute_batch_insert(doris_conn, insert_sql, rows_data)

def query_annotations(
    doris_conn: Connection,
    shots: List[int],
    table_names: List[str] | str,
    columns: Optional[List[str]] = None,
    all_info: bool = False
) -> List[Dict[str, Any]]:
    """
    从 Doris 查询标注数据
    
    参数:
    ----
    doris_conn: Doris 连接对象
    shots: 炮号列表
    table_names: 表名列表
    columns: 指定列
    all_info: 是否返回所有信息
    
    返回:
    ----
    List[Dict]: 查询结果
    """
    result_list = []
    if not shots or not table_names:
        return result_list
    
    if isinstance(table_names, str):
        table_names = [table_names]
    
    try:
        # 去重炮号列表
        shot_set = list(set(shots))
        if not shot_set:
            return result_list
        
        for table in table_names:
            # 1. 检查表是否存在
            with doris_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                """, (DORIS_DATABASE, table))
                table_exists = cursor.fetchone()['count'] > 0
                
                if not table_exists:
                    print(f"警告: 表 {table} 不存在，跳过")
                    continue
            
            # 2. 确定要查询的列
            actual_columns = columns
            if columns is None:
                if all_info:
                    # 查询所有列
                    actual_columns = get_table_columns(doris_conn, table)
                else:
                    # 只返回常用列
                    actual_columns = []
                    possible_common_cols = [
                        "shot", "label", "feature", "start_time", "end_time",
                        "is_point", "annotation_id"
                    ]
                    # 取交集
                    table_cols = get_table_columns(doris_conn, table)
                    for col in possible_common_cols:
                        if col in table_cols:
                            actual_columns.append(col)
                    if not actual_columns:
                        continue
            
            # 3. 构造查询SQL
            col_str = ", ".join(f"`{col}`" for col in actual_columns)
            placeholders = ", ".join(["%s"] * len(shot_set))
            sql = f"""
                SELECT {col_str}
                FROM `{table}`
                WHERE shot IN ({placeholders})
                ORDER BY shot
            """
            
            with doris_conn.cursor() as cursor:
                cursor.execute(sql, shot_set)
                rows = cursor.fetchall()
                
                for row in rows:
                    row_dict = dict(row)  # DictCursor 返回字典
                    row_dict["table"] = table
                    result_list.append(row_dict)
        
        return result_list
    except Exception as e:
        print(f'导出标注数据错误: {e}')
        return []

def get_shots_single_table(
    doris_conn: Connection,
    table_name: str,
    min_duration: Optional[float] = None,
    max_duration: Optional[float] = None,
    feature_name: Optional[str] = None,
    label_name: Optional[str] = None,
    label_column_name: Optional[str] = 'label',
    has_feature: bool = True,
    has_label: bool = True
) -> List[int]:
    """
    根据条件从指定表中筛选符合条件的唯一炮号，并按升序返回
    
    参数:
    ----
    table_name: str 需要查询的表名
    min_duration: float 允许的最小持续时间(end_time - start_time)
    max_duration: float 允许的最大持续时间
    feature_name: str 指定特征名称（仅当表为多标签组时有效）
    label_name: str 指定标签名称
    label_column_name: str label列的表头名，默认为"label"
    has_feature: bool 是否要求存在特征（True时要求存在，False时要求不存在）
    has_label: bool 是否要求存在标签（True时要求存在，False时要求不存在）
    
    返回:
    ----
    shots: List[int] 排序后的唯一炮号列表
    """
    try:
        with doris_conn.cursor() as cursor:
            # 1. 检查表是否存在
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (DORIS_DATABASE, table_name))
            if cursor.fetchone()['count'] == 0:
                raise ValueError(f"表 {table_name} 不存在")

            # 2. 动态构建查询条件
            conditions = []
            params = []
            
            # 持续时间条件
            if min_duration is not None or max_duration is not None:
                duration_clause = "(end_time - start_time)"
                if min_duration is not None:
                    conditions.append(f"{duration_clause} >= %s")
                    params.append(min_duration)
                if max_duration is not None:
                    conditions.append(f"{duration_clause} <= %s")
                    params.append(max_duration)
            
            # 特征条件（仅当表有多标签组时有效）
            table_columns = get_table_columns(doris_conn, table_name)
            if "feature" in table_columns and feature_name is not None:
                operator = "=" if has_feature else "!="
                conditions.append(f"feature {operator} %s")
                params.append(feature_name)
            elif "feature" not in table_columns and feature_name is not None:
                raise ValueError("该表不支持特征筛选")
            
            # 标签条件
            label_col = label_column_name if label_column_name in table_columns else None
            if label_col and label_name is not None:
                operator = "=" if has_label else "!="
                conditions.append(f"`{label_col}` {operator} %s")
                params.append(label_name)
            elif label_name is not None and label_col is None:
                raise ValueError("该表不支持标签筛选")

            # 3. 组合完整查询
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"""
                SELECT DISTINCT shot 
                FROM `{table_name}` 
                {where_clause}
                ORDER BY shot ASC
            """
            cursor.execute(sql, params)
            return [row['shot'] for row in cursor.fetchall()]

    except Exception as e:
        print(f"数据库错误: {e}")
        return []
