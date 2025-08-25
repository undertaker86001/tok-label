import pymysql
import pymysql.cursors
from pymysql.connections import Connection
from typing import Optional, Dict, Any, List, Sequence, Tuple
from datetime import datetime
import pytz
from ..config import (
    DORIS_FE_HOST, DORIS_FE_PORT, DORIS_USER, 
    DORIS_PASSWORD, DORIS_DATABASE
)

def connect_doris_database() -> Connection:
    """
    连接到 Doris 数据库
    
    返回:
    ----
    Connection: pymysql 连接对象
    """
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

def list_existing_tables(doris_conn: Connection, database: str = None) -> List[str]:
    """
    列出当前数据库中的所有表名
    
    参数:
    ----
    doris_conn: Doris 连接对象
    database: 数据库名，默认使用当前连接的数据库
    
    返回:
    ----
    List[str]: 表名列表
    """
    with doris_conn.cursor() as cursor:
        if database:
            cursor.execute("SHOW TABLES FROM `%s`", (database,))
        else:
            cursor.execute("SHOW TABLES")
        result = cursor.fetchall()
    return [row[f'Tables_in_{database or DORIS_DATABASE}'] for row in result]

def get_table_columns(
    doris_conn: Connection,
    table_name: str,
    database: str = None,
    name_only: bool = True,
    include_type: Optional[Sequence[str]] = None,
    exclude_columns: Optional[Sequence[str]] = None
) -> List[str]:
    """
    获取表的列信息
    
    参数:
    ----
    doris_conn: Doris 连接对象
    table_name: 表名
    database: 数据库名
    name_only: 是否只返回列名
    include_type: 仅包含指定类型的列
    exclude_columns: 排除的列名
    
    返回:
    ----
    List[str]: 列名列表或 (列名, 类型) 元组列表
    """
    db_name = database or DORIS_DATABASE
    
    with doris_conn.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (db_name, table_name))
        cols = cursor.fetchall()
    
    # 转换为元组列表
    column_info = [(row['COLUMN_NAME'], row['DATA_TYPE']) for row in cols]
    
    if include_type:
        include_type = set(t.lower() for t in include_type)
        column_info = [(c, t) for c, t in column_info if t.lower() in include_type]
    
    if exclude_columns:
        exclude_columns = set(exclude_columns)
        column_info = [(c, t) for c, t in column_info if c not in exclude_columns]
    
    return [c for c, _ in column_info] if name_only else column_info

def delete_table(
    doris_conn: Connection,
    table_name: str,
    database: str = None
):
    """
    删除数据库中的表
    
    参数:
    ----
    doris_conn: Doris 连接对象
    table_name: 表名
    database: 数据库名
    """
    db_name = database or DORIS_DATABASE
    
    with doris_conn.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS `{db_name}`.`{table_name}`")
        doris_conn.commit()

def string_to_datetime(
    date_time_str: str,
    timezone: str = "Asia/Shanghai"
) -> Optional[datetime]:
    """
    将时间字符串转换为 datetime 格式（适配 Doris）
    
    参数:
    ----
    date_time_str: 时间字符串
    timezone: 时区
    
    返回:
    ----
    datetime: 转换后的时间对象
    """
    if date_time_str is None:
        return None
    
    dt_utc = datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    dt_utc = dt_utc.replace(tzinfo=pytz.utc)
    
    # 转为指定时区
    target_tz = pytz.timezone(timezone)
    dt_target = dt_utc.astimezone(target_tz)
    return dt_target

def execute_batch_insert(
    doris_conn: Connection,
    sql: str,
    data: List[Tuple],
    batch_size: int = 1000
):
    """
    批量插入数据到 Doris
    
    参数:
    ----
    doris_conn: Doris 连接对象
    sql: 插入 SQL 语句
    data: 数据列表
    batch_size: 批次大小
    """
    with doris_conn.cursor() as cursor:
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            cursor.executemany(sql, batch)
        doris_conn.commit()
