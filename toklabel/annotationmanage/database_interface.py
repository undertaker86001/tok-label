from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd

class DatabaseInterface(ABC):
    """数据库操作统一接口"""
    
    @abstractmethod
    def connect(self):
        """建立数据库连接"""
        pass
    
    @abstractmethod
    def close(self):
        """关闭数据库连接"""
        pass
    
    @abstractmethod
    def create_annotation_table(
        self, 
        table_name: str, 
        multi_label_group: bool = False,
        with_label: bool = True,
        label_name: str = None,
        unique_shot: bool = False,
        point_allowed: bool = True
    ):
        """创建标注表"""
        pass
    
    @abstractmethod
    def insert_annotations(
        self, 
        table_name: str, 
        data_list: List[Dict[str, Any]],
        on_conflict: Optional[str] = None
    ):
        """插入标注数据"""
        pass
    
    @abstractmethod
    def query_annotations(
        self, 
        shots: List[int],
        table_names: Union[List[str], str],
        columns: Optional[List[str]] = None,
        all_info: bool = False
    ) -> List[Dict[str, Any]]:
        """查询标注数据"""
        pass
    
    @abstractmethod
    def export_data(
        self,
        shots: Union[int, List[int]], 
        name_table_columns: Dict[str, Tuple[str, List[str]]], 
        t_min: float = float('-inf'), 
        t_max: float = float('inf'), 
        resolution: float = 1e-3
    ) -> Dict[Union[int, str], pd.DataFrame]:
        """导出数据"""
        pass
    
    @abstractmethod
    def list_tables(self, database: str = None) -> List[str]:
        """列出所有表"""
        pass
    
    @abstractmethod
    def get_table_columns(
        self, 
        table_name: str, 
        database: str = None,
        name_only: bool = True
    ) -> List[str]:
        """获取表列信息"""
        pass
    
    @abstractmethod
    def delete_table(self, table_name: str, database: str = None):
        """删除表"""
        pass
