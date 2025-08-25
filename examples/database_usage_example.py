"""
数据库工厂模式使用示例
演示如何使用统一接口操作 PostgreSQL 和 Doris 数据库
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from toklabel import DatabaseFactory

def example_basic_usage():
    """基础使用示例"""
    print("=== 基础数据库操作示例 ===")
    
    # 1. 使用默认数据库类型
    print("1. 创建标注表（使用默认数据库）")
    try:
        DatabaseFactory.create_annotation_table(
            table_name="example_annotations",
            multi_label_group=False,
            with_label=True,
            unique_shot=False
        )
        print("   ✓ 标注表创建成功")
    except Exception as e:
        print(f"   ✗ 标注表创建失败: {e}")
    
    # 2. 插入标注数据
    print("2. 插入标注数据")
    sample_data = [
        {
            "shot": 240830026,
            "label": "disruption",
            "start_time": 0.1,
            "end_time": 0.5,
            "annotator": 1,
            "annotation_id": 1001
        },
        {
            "shot": 240830027,
            "label": "normal",
            "start_time": 0.2,
            "end_time": 0.8,
            "annotator": 1,
            "annotation_id": 1002
        }
    ]
    
    try:
        DatabaseFactory.insert_annotations("example_annotations", sample_data)
        print("   ✓ 标注数据插入成功")
    except Exception as e:
        print(f"   ✗ 标注数据插入失败: {e}")
    
    # 3. 查询标注数据
    print("3. 查询标注数据")
    try:
        annotations = DatabaseFactory.query_annotations(
            shots=[240830026, 240830027],
            table_names="example_annotations",
            all_info=True
        )
        print(f"   ✓ 查询到 {len(annotations)} 条标注数据")
    except Exception as e:
        print(f"   ✗ 查询标注数据失败: {e}")
    
    # 4. 列出所有表
    print("4. 列出所有表")
    try:
        tables = DatabaseFactory.list_tables()
        print(f"   ✓ 数据库中共有 {len(tables)} 个表")
    except Exception as e:
        print(f"   ✗ 列出表失败: {e}")

def example_database_switching():
    """数据库切换示例"""
    print("\n=== 数据库切换示例 ===")
    
    # 1. 使用 PostgreSQL
    print("1. 使用 PostgreSQL 创建表")
    try:
        DatabaseFactory.create_annotation_table(
            table_name="pg_test_table",
            with_label=True,
            db_type="postgresql"
        )
        print("   ✓ PostgreSQL 表创建成功")
    except Exception as e:
        print(f"   ✗ PostgreSQL 表创建失败: {e}")
    
    # 2. 使用 Doris
    print("2. 使用 Doris 创建表")
    try:
        DatabaseFactory.create_annotation_table(
            table_name="doris_test_table",
            with_label=True,
            db_type="doris"
        )
        print("   ✓ Doris 表创建成功")
    except Exception as e:
        print(f"   ✗ Doris 表创建失败: {e}")

def example_data_export():
    """数据导出示例"""
    print("\n=== 数据导出示例 ===")
    
    # 定义要导出的表和列
    name_table_columns = {
        "ammeter": ("ammeter", ["CS1", "PFP1"]),
        "flux_loop": ("flux_loop", [1, 2, 8])
    }
    
    shots = [240830026, 240830027]
    
    # 1. 从 PostgreSQL 导出
    print("1. 从 PostgreSQL 导出数据")
    try:
        data = DatabaseFactory.export_data(
            shots=shots,
            name_table_columns=name_table_columns,
            t_min=0.0,
            t_max=1.0,
            resolution=0.001,
            db_type="postgresql"
        )
        print(f"   ✓ PostgreSQL 导出成功，获得 {len(data)} 个炮号的数据")
    except Exception as e:
        print(f"   ✗ PostgreSQL 导出失败: {e}")
    
    # 2. 从 Doris 导出
    print("2. 从 Doris 导出数据")
    try:
        data = DatabaseFactory.export_data(
            shots=shots,
            name_table_columns=name_table_columns,
            t_min=0.0,
            t_max=1.0,
            resolution=0.001,
            db_type="doris"
        )
        print(f"   ✓ Doris 导出成功，获得 {len(data)} 个炮号的数据")
    except Exception as e:
        print(f"   ✗ Doris 导出失败: {e}")

def example_connection_management():
    """连接管理示例"""
    print("\n=== 连接管理示例 ===")
    
    # 1. 获取不同类型的适配器
    print("1. 获取不同类型的适配器")
    try:
        pg_adapter = DatabaseFactory.get_adapter('postgresql')
        doris_adapter = DatabaseFactory.get_adapter('doris')
        
        print(f"   ✓ PostgreSQL 适配器: {type(pg_adapter).__name__}")
        print(f"   ✓ Doris 适配器: {type(doris_adapter).__name__}")
        
        # 验证它们是不同的实例
        if pg_adapter is not doris_adapter:
            print("   ✓ 适配器实例不同（符合预期）")
        else:
            print("   ✗ 适配器实例相同（不符合预期）")
            
    except Exception as e:
        print(f"   ✗ 获取适配器失败: {e}")
    
    # 2. 测试连接池功能
    print("2. 测试连接池功能")
    try:
        adapter1 = DatabaseFactory.get_adapter('postgresql')
        adapter2 = DatabaseFactory.get_adapter('postgresql')
        
        if adapter1 is adapter2:
            print("   ✓ 连接池工作正常（返回相同实例）")
        else:
            print("   ✓ 连接池未启用（返回不同实例）")
            
    except Exception as e:
        print(f"   ✗ 连接池测试失败: {e}")

def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    # 1. 测试不支持的数据库类型
    print("1. 测试不支持的数据库类型")
    try:
        DatabaseFactory.get_adapter('mysql')
        print("   ✗ 应该抛出异常但没有")
    except ValueError as e:
        print(f"   ✓ 正确抛出异常: {e}")
    except Exception as e:
        print(f"   ✗ 抛出错误的异常类型: {type(e).__name__}")
    
    # 2. 测试无效的表名
    print("2. 测试无效的表名")
    try:
        DatabaseFactory.create_annotation_table(
            table_name="",  # 空表名
            with_label=True
        )
        print("   ✗ 应该抛出异常但没有")
    except Exception as e:
        print(f"   ✓ 正确抛出异常: {e}")

def main():
    """主函数"""
    print("TOKLABEL 数据库工厂模式使用示例")
    print("=" * 50)
    
    try:
        # 运行所有示例
        example_basic_usage()
        example_database_switching()
        example_data_export()
        example_connection_management()
        example_error_handling()
        
        print("\n" + "=" * 50)
        print("所有示例运行完成！")
        
    except Exception as e:
        print(f"\n示例运行出错: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理连接
        try:
            DatabaseFactory.close_all_connections()
            print("\n所有数据库连接已关闭")
        except Exception as e:
            print(f"关闭连接时出错: {e}")

if __name__ == "__main__":
    main()
