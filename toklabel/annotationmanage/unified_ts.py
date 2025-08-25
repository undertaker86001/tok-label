"""
统一的标注管理接口
整合 PostgreSQL 和 Doris 的标注表管理功能
"""

from typing import Optional, Dict, Any, List, Sequence, Union
from datetime import datetime
import pytz
from .database_factory import DatabaseFactory
from .database_interface import DatabaseInterface

class UnifiedAnnotationManager:
    """统一的标注管理器，支持 PostgreSQL 和 Doris"""
    
    def __init__(self, db_type: str = None):
        """
        初始化标注管理器
        
        参数:
        ----
        db_type: 数据库类型，如果为 None 则使用配置中的默认类型
        """
        self.db_type = db_type
        self.adapter = DatabaseFactory.get_adapter(db_type)
    
    def create_annotation_table(
        self,
        table_name: str,
        multi_label_group: bool = False,
        with_label: bool = True,
        label_name: str = None,
        unique_shot: bool = False,
        point_allowed: bool = True
    ):
        """
        创建标注表（统一接口）
        
        参数:
        ----
        table_name: 表名
        multi_label_group: 是否涉及多个标签组
        with_label: 是否包含 label 字段
        label_name: label 列的名称
        unique_shot: 是否为 shot 加唯一约束
        point_allowed: 是否允许存储 is_point
        """
        return self.adapter.create_annotation_table(
            table_name, multi_label_group, with_label,
            label_name, unique_shot, point_allowed
        )
    
    def insert_annotations(
        self,
        table_name: str,
        data_list: List[Dict[str, Any]],
        on_conflict: Optional[str] = None
    ):
        """
        插入标注数据（统一接口）
        
        参数:
        ----
        table_name: 表名
        data_list: 数据列表
        on_conflict: 冲突处理策略
        """
        return self.adapter.insert_annotations(table_name, data_list, on_conflict)
    
    def query_annotations(
        self,
        shots: List[int],
        table_names: Union[List[str], str],
        columns: Optional[List[str]] = None,
        all_info: bool = False
    ) -> List[Dict[str, Any]]:
        """
        查询标注数据（统一接口）
        
        参数:
        ----
        shots: 炮号列表
        table_names: 表名列表或单个表名
        columns: 指定列
        all_info: 是否返回所有信息
        
        返回:
        ----
        List[Dict]: 查询结果
        """
        return self.adapter.query_annotations(shots, table_names, columns, all_info)
    
    def get_shots_single_table(
        self,
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
        根据条件从指定表中筛选符合条件的唯一炮号（统一接口）
        
        参数:
        ----
        table_name: 表名
        min_duration: 允许的最小持续时间
        max_duration: 允许的最大持续时间
        feature_name: 指定特征名称
        label_name: 指定标签名称
        label_column_name: label列的表头名
        has_feature: 是否要求存在特征
        has_label: 是否要求存在标签
        
        返回:
        ----
        List[int]: 排序后的唯一炮号列表
        """
        # 这里需要根据数据库类型调用不同的实现
        if self.db_type == 'doris' or DatabaseFactory.is_doris(self.db_type):
            # 使用 Doris 实现
            from .doris_ts import get_shots_single_table as doris_get_shots
            conn = self.adapter.connect()
            return doris_get_shots(
                conn, table_name, min_duration, max_duration,
                feature_name, label_name, label_column_name,
                has_feature, has_label
            )
        else:
            # 使用 PostgreSQL 实现
            from .ts import get_shots_single_table as pg_get_shots
            conn = self.adapter.connect()
            return pg_get_shots(
                conn, table_name, min_duration, max_duration,
                feature_name, label_name, label_column_name,
                has_feature, has_label
            )
    
    def batch_insert_with_upsert(
        self,
        table_name: str,
        data_list: List[Dict[str, Any]],
        upsert_keys: List[str],
        batch_size: int = 1000
    ):
        """
        批量插入数据，支持 UPSERT 操作
        
        参数:
        ----
        table_name: 表名
        data_list: 数据列表
        upsert_keys: UPSERT 的键列表
        batch_size: 批次大小
        """
        if not data_list:
            return
        
        # 分批处理
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            
            if self.db_type == 'doris' or DatabaseFactory.is_doris(self.db_type):
                # Doris 使用 UNIQUE KEY 模型处理冲突
                self.adapter.insert_annotations(table_name, batch)
            else:
                # PostgreSQL 使用 ON CONFLICT 处理
                upsert_constraint = f"({', '.join(upsert_keys)})"
                self.adapter.insert_annotations(table_name, batch, upsert_constraint)
    
    def get_table_schema(
        self,
        table_name: str,
        include_types: bool = True
    ) -> Dict[str, Any]:
        """
        获取表的完整结构信息
        
        参数:
        ----
        table_name: 表名
        include_types: 是否包含数据类型信息
        
        返回:
        ----
        Dict: 表结构信息
        """
        columns = self.adapter.get_table_columns(
            table_name, name_only=not include_types
        )
        
        # 获取表的其他信息
        conn = self.adapter.connect()
        table_info = {
            "table_name": table_name,
            "columns": columns,
            "database_type": self.db_type or DatabaseFactory.get_adapter().__class__.__name__
        }
        
        # 根据数据库类型获取额外信息
        if self.db_type == 'doris' or DatabaseFactory.is_doris(self.db_type):
            # Doris 特有的表信息
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT TABLE_TYPE, ENGINE, TABLE_ROWS, AVG_ROW_LENGTH
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                    """, (table_name,))
                    result = cursor.fetchone()
                    if result:
                        table_info.update({
                            "table_type": result['TABLE_TYPE'],
                            "engine": result['ENGINE'],
                            "estimated_rows": result['TABLE_ROWS'],
                            "avg_row_length": result['AVG_ROW_LENGTH']
                        })
            except Exception as e:
                table_info["doris_info_error"] = str(e)
        else:
            # PostgreSQL 特有的表信息
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT schemaname, tablename, tableowner, tablespace
                        FROM pg_tables
                        WHERE tablename = %s
                    """, (table_name,))
                    result = cursor.fetchone()
                    if result:
                        table_info.update({
                            "schema": result[0],
                            "owner": result[2],
                            "tablespace": result[3]
                        })
            except Exception as e:
                table_info["postgresql_info_error"] = str(e)
        
        return table_info
    
    def optimize_table(
        self,
        table_name: str,
        optimization_type: str = "auto"
    ):
        """
        优化表性能
        
        参数:
        ----
        table_name: 表名
        optimization_type: 优化类型
        """
        conn = self.adapter.connect()
        
        if self.db_type == 'doris' or DatabaseFactory.is_doris(self.db_type):
            # Doris 表优化
            try:
                with conn.cursor() as cursor:
                    if optimization_type == "compact":
                        # 执行 COMPACT 操作
                        cursor.execute(f"ADMIN SHOW PROC '/compactions'")
                        print(f"表 {table_name} 的压缩状态已查询")
                    elif optimization_type == "analyze":
                        # 执行 ANALYZE 操作
                        cursor.execute(f"ANALYZE TABLE `{table_name}`")
                        print(f"表 {table_name} 的统计信息已更新")
                    else:
                        # 自动优化
                        cursor.execute(f"ADMIN SHOW PROC '/compactions'")
                        print(f"表 {table_name} 的优化状态已查询")
            except Exception as e:
                print(f"Doris 表优化失败: {e}")
        else:
            # PostgreSQL 表优化
            try:
                with conn.cursor() as cursor:
                    if optimization_type == "vacuum":
                        cursor.execute(f"VACUUM ANALYZE {table_name}")
                        print(f"表 {table_name} 的 VACUUM ANALYZE 已完成")
                    elif optimization_type == "reindex":
                        cursor.execute(f"REINDEX TABLE {table_name}")
                        print(f"表 {table_name} 的索引重建已完成")
                    else:
                        # 自动优化
                        cursor.execute(f"VACUUM ANALYZE {table_name}")
                        print(f"表 {table_name} 的自动优化已完成")
            except Exception as e:
                print(f"PostgreSQL 表优化失败: {e}")
    
    def export_annotations_to_csv(
        self,
        table_name: str,
        shots: List[int],
        output_file: str,
        columns: Optional[List[str]] = None,
        include_headers: bool = True
    ):
        """
        将标注数据导出为 CSV 文件
        
        参数:
        ----
        table_name: 表名
        shots: 炮号列表
        output_file: 输出文件路径
        columns: 指定列
        include_headers: 是否包含表头
        """
        import csv
        
        # 查询数据
        annotations = self.query_annotations(shots, table_name, columns, all_info=True)
        
        if not annotations:
            print(f"没有找到炮号 {shots} 的标注数据")
            return
        
        # 写入 CSV 文件
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            if annotations:
                fieldnames = list(annotations[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if include_headers:
                    writer.writeheader()
                
                writer.writerows(annotations)
        
        print(f"标注数据已导出到 {output_file}，共 {len(annotations)} 条记录")
    
    def get_annotation_statistics(
        self,
        table_name: str,
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取标注数据的统计信息
        
        参数:
        ----
        table_name: 表名
        group_by: 分组字段（如 'label', 'feature'）
        
        返回:
        ----
        Dict: 统计信息
        """
        conn = self.adapter.connect()
        
        try:
            if self.db_type == 'doris' or DatabaseFactory.is_doris(self.db_type):
                # Doris 统计查询
                with conn.cursor() as cursor:
                    if group_by:
                        cursor.execute(f"""
                            SELECT `{group_by}`, COUNT(*) as count
                            FROM `{table_name}`
                            GROUP BY `{group_by}`
                            ORDER BY count DESC
                        """)
                    else:
                        cursor.execute(f"""
                            SELECT 
                                COUNT(*) as total_annotations,
                                COUNT(DISTINCT shot) as unique_shots,
                                COUNT(DISTINCT annotator) as unique_annotators,
                                AVG(end_time - start_time) as avg_duration
                            FROM `{table_name}`
                        """)
                    
                    result = cursor.fetchall()
                    
                    if group_by:
                        return {
                            "group_by": group_by,
                            "distribution": result
                        }
                    else:
                        return result[0] if result else {}
            else:
                # PostgreSQL 统计查询
                with conn.cursor() as cursor:
                    if group_by:
                        cursor.execute(f"""
                            SELECT {group_by}, COUNT(*) as count
                            FROM {table_name}
                            GROUP BY {group_by}
                            ORDER BY count DESC
                        """)
                    else:
                        cursor.execute(f"""
                            SELECT 
                                COUNT(*) as total_annotations,
                                COUNT(DISTINCT shot) as unique_shots,
                                COUNT(DISTINCT annotator) as unique_annotators,
                                AVG(end_time - start_time) as avg_duration
                            FROM {table_name}
                        """)
                    
                    result = cursor.fetchall()
                    
                    if group_by:
                        return {
                            "group_by": group_by,
                            "distribution": result
                        }
                    else:
                        return result[0] if result else {}
                        
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {"error": str(e)}
    
    def close(self):
        """关闭数据库连接"""
        self.adapter.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
