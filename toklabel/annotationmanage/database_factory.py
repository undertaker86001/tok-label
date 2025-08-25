from typing import Union, Type
from ..config import DATABASE_TYPE, ENABLE_CONNECTION_POOLING
from .database_interface import DatabaseInterface
from .postgres_adapter import PostgreSQLAdapter
from .doris_adapter import DorisAdapter
import psycopg2
import pymysql

class DatabaseFactory:
    """数据库工厂类，根据配置选择数据库类型"""
    
    _instance = None
    _adapters = {}
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(DatabaseFactory, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_adapter(cls, db_type: str = None) -> DatabaseInterface:
        """
        根据配置获取数据库适配器
        
        参数:
        ----
        db_type: 数据库类型，如果为 None 则使用配置中的默认类型
        
        返回:
        ----
        DatabaseInterface: 数据库适配器实例
        """
        db_type = db_type or DATABASE_TYPE
        db_type = db_type.lower()
        
        # 如果启用连接池，复用适配器实例
        if ENABLE_CONNECTION_POOLING and db_type in cls._adapters:
            return cls._adapters[db_type]
        
        if db_type == 'doris':
            adapter = DorisAdapter()
        elif db_type == 'postgresql':
            adapter = PostgreSQLAdapter()
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")
        
        # 缓存适配器实例
        if ENABLE_CONNECTION_POOLING:
            cls._adapters[db_type] = adapter
        
        return adapter
    
    @classmethod
    def get_connection(cls, db_type: str = None):
        """
        根据配置获取数据库连接
        
        参数:
        ----
        db_type: 数据库类型
        
        返回:
        ----
        数据库连接对象
        """
        if db_type is None:
            db_type = DATABASE_TYPE
            
        if db_type.lower() == 'doris':
            from .doris_utils import connect_doris_database
            return connect_doris_database()
        else:
            from .utils import connect_annotation_database
            return connect_annotation_database()
    
    @classmethod
    def get_ts_module(cls):
        """
        根据配置获取对应的时序数据模块
        
        返回:
        ----
        对应的 ts 模块
        """
        if DATABASE_TYPE.lower() == 'doris':
            from . import doris_ts
            return doris_ts
        else:
            from . import ts
            return ts
    
    @classmethod
    def create_annotation_table(
        cls,
        table_name: str,
        multi_label_group: bool = False,
        with_label: bool = True,
        label_name: str = None,
        unique_shot: bool = False,
        point_allowed: bool = True,
        db_type: str = None
    ):
        """统一的创建标注表接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.create_annotation_table(
            table_name, multi_label_group, with_label, 
            label_name, unique_shot, point_allowed
        )
    
    @classmethod
    def insert_annotations(
        cls,
        table_name: str,
        data_list: list,
        on_conflict: str = None,
        db_type: str = None
    ):
        """统一的插入标注数据接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.insert_annotations(table_name, data_list, on_conflict)
    
    @classmethod
    def query_annotations(
        cls,
        shots: list,
        table_names: Union[list, str],
        columns: list = None,
        all_info: bool = False,
        db_type: str = None
    ):
        """统一的查询标注数据接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.query_annotations(shots, table_names, columns, all_info)
    
    @classmethod
    def export_data(
        cls,
        shots: Union[int, list],
        name_table_columns: dict,
        t_min: float = float('-inf'),
        t_max: float = float('inf'),
        resolution: float = 1e-3,
        db_type: str = None
    ):
        """统一的数据导出接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.export_data(shots, name_table_columns, t_min, t_max, resolution)
    
    @classmethod
    def list_tables(cls, database: str = None, db_type: str = None):
        """统一的列表表接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.list_tables(database)
    
    @classmethod
    def get_table_columns(
        cls,
        table_name: str,
        database: str = None,
        name_only: bool = True,
        db_type: str = None
    ):
        """统一的获取表列信息接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.get_table_columns(table_name, database, name_only)
    
    @classmethod
    def delete_table(cls, table_name: str, database: str = None, db_type: str = None):
        """统一的删除表接口"""
        adapter = cls.get_adapter(db_type)
        return adapter.delete_table(table_name, database)
    
    @classmethod
    def is_doris(cls, db_type: str = None) -> bool:
        """判断当前是否使用 Doris 数据库"""
        db_type = db_type or DATABASE_TYPE
        return db_type.lower() == 'doris'
    
    @classmethod
    def is_postgresql(cls, db_type: str = None) -> bool:
        """判断当前是否使用 PostgreSQL 数据库"""
        db_type = db_type or DATABASE_TYPE
        return db_type.lower() == 'postgresql'
    
    @classmethod
    def close_all_connections(cls):
        """关闭所有缓存的连接"""
        for adapter in cls._adapters.values():
            try:
                adapter.close()
            except Exception as e:
                print(f"关闭连接时出错: {e}")
        cls._adapters.clear()
