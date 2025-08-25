import pymysql
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd
from .database_interface import DatabaseInterface
from .doris_utils import connect_doris_database, get_table_columns, list_existing_tables, delete_table
from . import doris_ts
from ..config import DORIS_QUERY_TIMEOUT, DORIS_BATCH_SIZE

class DorisAdapter(DatabaseInterface):
    """Doris 数据库适配器"""
    
    def __init__(self):
        self.conn = None
        self.query_timeout = DORIS_QUERY_TIMEOUT
        self.batch_size = DORIS_BATCH_SIZE
    
    def connect(self):
        """建立 Doris 连接"""
        if self.conn is None:
            self.conn = connect_doris_database()
        return self.conn
    
    def close(self):
        """关闭 Doris 连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def create_annotation_table(
        self, 
        table_name: str, 
        multi_label_group: bool = False,
        with_label: bool = True,
        label_name: str = None,
        unique_shot: bool = False,
        point_allowed: bool = True
    ):
        """创建 Doris 标注表"""
        conn = self.connect()
        return doris_ts.create_annotation_table(
            conn, table_name, multi_label_group, 
            with_label, label_name, unique_shot, point_allowed
        )
    
    def insert_annotations(
        self, 
        table_name: str, 
        data_list: List[Dict[str, Any]],
        on_conflict: Optional[str] = None
    ):
        """插入标注数据到 Doris"""
        conn = self.connect()
        return doris_ts.insert_annotations(conn, table_name, data_list, on_conflict)
    
    def query_annotations(
        self, 
        shots: List[int],
        table_names: Union[List[str], str],
        columns: Optional[List[str]] = None,
        all_info: bool = False
    ) -> List[Dict[str, Any]]:
        """从 Doris 查询标注数据"""
        conn = self.connect()
        return doris_ts.query_annotations(conn, shots, table_names, columns, all_info)
    
    def export_data(
        self,
        shots: Union[int, List[int]], 
        name_table_columns: Dict[str, Tuple[str, List[str]]], 
        t_min: float = float('-inf'), 
        t_max: float = float('inf'), 
        resolution: float = 1e-3
    ) -> Dict[Union[int, str], pd.DataFrame]:
        """从 Doris 导出数据"""
        from ..utils import export_data as utils_export_data
        return utils_export_data(
            shots, name_table_columns, t_min, t_max, resolution, 'doris'
        )
    
    def list_tables(self, database: str = None) -> List[str]:
        """列出 Doris 中的所有表"""
        conn = self.connect()
        return list_existing_tables(conn, database)
    
    def get_table_columns(
        self, 
        table_name: str, 
        database: str = None,
        name_only: bool = True
    ) -> List[str]:
        """获取 Doris 表列信息"""
        conn = self.connect()
        return get_table_columns(conn, table_name, database, name_only)
    
    def delete_table(self, table_name: str, database: str = None):
        """删除 Doris 表"""
        conn = self.connect()
        return delete_table(conn, table_name, database)
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
