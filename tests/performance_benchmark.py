"""
性能对比测试工具
对比 PostgreSQL 和 Doris 数据库在不同场景下的性能表现
"""

import time
import sys
import os
from typing import Dict, List, Any, Tuple
import statistics

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from toklabel.annotationmanage.database_factory import DatabaseFactory
from toklabel.annotationmanage.unified_ts import UnifiedAnnotationManager

class PerformanceBenchmark:
    """性能对比测试工具"""
    
    def __init__(self):
        """初始化性能测试工具"""
        self.results = {}
    
    def benchmark_table_creation(self, table_names: List[str], iterations: int = 5) -> Dict[str, Any]:
        """
        测试表创建性能
        
        参数:
        ----
        table_names: 要创建的表名列表
        iterations: 测试迭代次数
        
        返回:
        ----
        Dict: 性能测试结果
        """
        print("开始表创建性能测试...")
        
        results = {
            'postgresql': {'times': [], 'success': True},
            'doris': {'times': [], 'success': True}
        }
        
        for db_type in ['postgresql', 'doris']:
            print(f"测试 {db_type} 表创建性能...")
            
            try:
                for i in range(iterations):
                    start_time = time.time()
                    
                    for table_name in table_names:
                        test_table_name = f"{table_name}_benchmark_{i}"
                        
                        try:
                            DatabaseFactory.create_annotation_table(
                                test_table_name,
                                multi_label_group=True,
                                with_label=True,
                                db_type=db_type
                            )
                            
                            # 清理测试表
                            DatabaseFactory.delete_table(test_table_name, db_type=db_type)
                            
                        except Exception as e:
                            print(f"表创建失败: {e}")
                            results[db_type]['success'] = False
                            break
                    
                    if results[db_type]['success']:
                        end_time = time.time()
                        duration = end_time - start_time
                        results[db_type]['times'].append(duration)
                        print(f"  迭代 {i+1}: {duration:.4f} 秒")
                    
            except Exception as e:
                print(f"{db_type} 测试失败: {e}")
                results[db_type]['success'] = False
        
        # 计算统计信息
        for db_type in results:
            if results[db_type]['success'] and results[db_type]['times']:
                times = results[db_type]['times']
                results[db_type].update({
                    'mean': statistics.mean(times),
                    'median': statistics.median(times),
                    'min': min(times),
                    'max': max(times),
                    'std': statistics.stdev(times) if len(times) > 1 else 0
                })
        
        self.results['table_creation'] = results
        return results
    
    def benchmark_data_insertion(
        self, 
        table_name: str, 
        data_sizes: List[int], 
        iterations: int = 3
    ) -> Dict[str, Any]:
        """
        测试数据插入性能
        
        参数:
        ----
        table_name: 表名
        data_sizes: 要测试的数据量列表
        iterations: 每个数据量的测试次数
        
        返回:
        ----
        Dict: 性能测试结果
        """
        print("开始数据插入性能测试...")
        
        results = {
            'postgresql': {},
            'doris': {}
        }
        
        for db_type in ['postgresql', 'doris']:
            print(f"测试 {db_type} 数据插入性能...")
            results[db_type] = {}
            
            try:
                for data_size in data_sizes:
                    print(f"  测试数据量: {data_size}")
                    results[db_type][data_size] = {'times': [], 'success': True}
                    
                    for i in range(iterations):
                        # 创建测试表
                        test_table_name = f"{table_name}_insert_benchmark_{data_size}_{i}"
                        
                        try:
                            DatabaseFactory.create_annotation_table(
                                test_table_name,
                                multi_label_group=False,
                                with_label=True,
                                db_type=db_type
                            )
                            
                            # 生成测试数据
                            test_data = self._generate_test_data(data_size)
                            
                            # 测试插入性能
                            start_time = time.time()
                            DatabaseFactory.insert_annotations(
                                test_table_name, test_data, db_type=db_type
                            )
                            end_time = time.time()
                            
                            duration = end_time - start_time
                            results[db_type][data_size]['times'].append(duration)
                            
                            print(f"    迭代 {i+1}: {duration:.4f} 秒")
                            
                            # 清理测试表
                            DatabaseFactory.delete_table(test_table_name, db_type=db_type)
                            
                        except Exception as e:
                            print(f"    插入测试失败: {e}")
                            results[db_type][data_size]['success'] = False
                            break
                    
                    # 计算该数据量的统计信息
                    if results[db_type][data_size]['success'] and results[db_type][data_size]['times']:
                        times = results[db_type][data_size]['times']
                        results[db_type][data_size].update({
                            'mean': statistics.mean(times),
                            'median': statistics.median(times),
                            'min': min(times),
                            'max': max(times),
                            'throughput': data_size / statistics.mean(times)  # 记录/秒
                        })
                        
            except Exception as e:
                print(f"{db_type} 插入测试失败: {e}")
        
        self.results['data_insertion'] = results
        return results
    
    def benchmark_data_query(
        self, 
        table_name: str, 
        query_scenarios: List[Dict], 
        iterations: int = 3
    ) -> Dict[str, Any]:
        """
        测试数据查询性能
        
        参数:
        ----
        table_name: 表名
        query_scenarios: 查询场景列表
        iterations: 每个场景的测试次数
        
        返回:
        ----
        Dict: 性能测试结果
        """
        print("开始数据查询性能测试...")
        
        results = {
            'postgresql': {},
            'doris': {}
        }
        
        for db_type in ['postgresql', 'doris']:
            print(f"测试 {db_type} 数据查询性能...")
            results[db_type] = {}
            
            try:
                for scenario in query_scenarios:
                    scenario_name = scenario['name']
                    print(f"  测试场景: {scenario_name}")
                    results[db_type][scenario_name] = {'times': [], 'success': True}
                    
                    for i in range(iterations):
                        try:
                            # 执行查询
                            start_time = time.time()
                            
                            if scenario['type'] == 'simple':
                                # 简单查询
                                DatabaseFactory.query_annotations(
                                    scenario['shots'], table_name, db_type=db_type
                                )
                            elif scenario['type'] == 'complex':
                                # 复杂查询（需要先创建表并插入数据）
                                test_table_name = f"{table_name}_query_benchmark_{i}"
                                self._setup_query_test_data(test_table_name, db_type)
                                
                                DatabaseFactory.query_annotations(
                                    scenario['shots'], test_table_name, 
                                    columns=scenario.get('columns'), 
                                    all_info=True, db_type=db_type
                                )
                                
                                # 清理测试表
                                DatabaseFactory.delete_table(test_table_name, db_type=db_type)
                            
                            end_time = time.time()
                            duration = end_time - start_time
                            results[db_type][scenario_name]['times'].append(duration)
                            
                            print(f"    迭代 {i+1}: {duration:.4f} 秒")
                            
                        except Exception as e:
                            print(f"    查询测试失败: {e}")
                            results[db_type][scenario_name]['success'] = False
                            break
                    
                    # 计算该场景的统计信息
                    if results[db_type][scenario_name]['success'] and results[db_type][scenario_name]['times']:
                        times = results[db_type][scenario_name]['times']
                        results[db_type][scenario_name].update({
                            'mean': statistics.mean(times),
                            'median': statistics.median(times),
                            'min': min(times),
                            'max': max(times)
                        })
                        
            except Exception as e:
                print(f"{db_type} 查询测试失败: {e}")
        
        self.results['data_query'] = results
        return results
    
    def benchmark_concurrent_operations(
        self, 
        table_name: str, 
        concurrent_users: List[int], 
        operations_per_user: int = 10
    ) -> Dict[str, Any]:
        """
        测试并发操作性能
        
        参数:
        ----
        table_name: 表名
        concurrent_users: 并发用户数列表
        operations_per_user: 每个用户的操作数
        
        返回:
        ----
        Dict: 性能测试结果
        """
        print("开始并发操作性能测试...")
        
        results = {
            'postgresql': {},
            'doris': {}
        }
        
        for db_type in ['postgresql', 'doris']:
            print(f"测试 {db_type} 并发操作性能...")
            results[db_type] = {}
            
            try:
                for user_count in concurrent_users:
                    print(f"  测试并发用户数: {user_count}")
                    results[db_type][user_count] = {'times': [], 'success': True}
                    
                    # 创建测试表
                    test_table_name = f"{table_name}_concurrent_benchmark_{user_count}"
                    
                    try:
                        DatabaseFactory.create_annotation_table(
                            test_table_name,
                            multi_label_group=False,
                            with_label=True,
                            db_type=db_type
                        )
                        
                        # 模拟并发操作
                        import threading
                        import queue
                        
                        result_queue = queue.Queue()
                        
                        def worker_operation(user_id):
                            """工作线程操作"""
                            try:
                                start_time = time.time()
                                
                                for op in range(operations_per_user):
                                    # 生成测试数据
                                    test_data = self._generate_test_data(10)  # 每次插入10条记录
                                    
                                    # 执行插入操作
                                    DatabaseFactory.insert_annotations(
                                        test_table_name, test_data, db_type=db_type
                                    )
                                
                                end_time = time.time()
                                duration = end_time - start_time
                                result_queue.put(('success', duration))
                                
                            except Exception as e:
                                result_queue.put(('error', str(e)))
                        
                        # 启动并发线程
                        threads = []
                        start_time = time.time()
                        
                        for user_id in range(user_count):
                            thread = threading.Thread(target=worker_operation, args=(user_id,))
                            threads.append(thread)
                            thread.start()
                        
                        # 等待所有线程完成
                        for thread in threads:
                            thread.join()
                        
                        end_time = time.time()
                        total_duration = end_time - start_time
                        
                        # 收集结果
                        success_count = 0
                        total_operation_time = 0
                        
                        while not result_queue.empty():
                            status, data = result_queue.get()
                            if status == 'success':
                                success_count += 1
                                total_operation_time += data
                        
                        if success_count > 0:
                            results[db_type][user_count].update({
                                'total_duration': total_duration,
                                'successful_users': success_count,
                                'avg_operation_time': total_operation_time / success_count,
                                'throughput': (success_count * operations_per_user) / total_duration
                            })
                        
                        print(f"    成功用户: {success_count}/{user_count}, 总耗时: {total_duration:.4f} 秒")
                        
                        # 清理测试表
                        DatabaseFactory.delete_table(test_table_name, db_type=db_type)
                        
                    except Exception as e:
                        print(f"    并发测试失败: {e}")
                        results[db_type][user_count]['success'] = False
                        
            except Exception as e:
                print(f"{db_type} 并发测试失败: {e}")
        
        self.results['concurrent_operations'] = results
        return results
    
    def generate_report(self) -> str:
        """生成性能测试报告"""
        report = []
        report.append("=" * 80)
        report.append("TOKLABEL 数据库性能对比测试报告")
        report.append("=" * 80)
        report.append("")
        
        for test_name, test_results in self.results.items():
            report.append(f"测试项目: {test_name}")
            report.append("-" * 40)
            
            if test_name == 'table_creation':
                self._add_table_creation_report(report, test_results)
            elif test_name == 'data_insertion':
                self._add_data_insertion_report(report, test_results)
            elif test_name == 'data_query':
                self._add_data_query_report(report, test_results)
            elif test_name == 'concurrent_operations':
                self._add_concurrent_report(report, test_results)
            
            report.append("")
        
        # 添加总体性能对比
        report.append("总体性能对比")
        report.append("-" * 40)
        self._add_overall_comparison(report)
        
        return "\n".join(report)
    
    def _add_table_creation_report(self, report: List[str], results: Dict):
        """添加表创建性能报告"""
        for db_type, data in results.items():
            if data['success'] and 'mean' in data:
                report.append(f"{db_type.upper()}:")
                report.append(f"  平均耗时: {data['mean']:.4f} 秒")
                report.append(f"  中位数: {data['median']:.4f} 秒")
                report.append(f"  标准差: {data['std']:.4f} 秒")
            else:
                report.append(f"{db_type.upper()}: 测试失败")
    
    def _add_data_insertion_report(self, report: List[str], results: Dict):
        """添加数据插入性能报告"""
        for db_type, data_sizes in results.items():
            report.append(f"{db_type.upper()}:")
            for data_size, metrics in data_sizes.items():
                if metrics['success'] and 'mean' in metrics:
                    report.append(f"  {data_size} 条记录:")
                    report.append(f"    平均耗时: {metrics['mean']:.4f} 秒")
                    report.append(f"    吞吐量: {metrics['throughput']:.2f} 记录/秒")
    
    def _add_data_query_report(self, report: List[str], results: Dict):
        """添加数据查询性能报告"""
        for db_type, scenarios in results.items():
            report.append(f"{db_type.upper()}:")
            for scenario_name, metrics in scenarios.items():
                if metrics['success'] and 'mean' in metrics:
                    report.append(f"  {scenario_name}: {metrics['mean']:.4f} 秒")
    
    def _add_concurrent_report(self, report: List[str], results: Dict):
        """添加并发操作性能报告"""
        for db_type, user_counts in results.items():
            report.append(f"{db_type.upper()}:")
            for user_count, metrics in user_counts.items():
                if 'throughput' in metrics:
                    report.append(f"  {user_count} 用户: {metrics['throughput']:.2f} 操作/秒")
    
    def _add_overall_comparison(self, report: List[str]):
        """添加总体性能对比"""
        # 这里可以添加更复杂的性能对比分析
        report.append("性能建议:")
        report.append("- 小规模项目: 推荐使用 PostgreSQL")
        report.append("- 大数据量分析: 推荐使用 Doris")
        report.append("- 高并发写入: 推荐使用 PostgreSQL")
        report.append("- 复杂查询分析: 推荐使用 Doris")
    
    def _generate_test_data(self, size: int) -> List[Dict[str, Any]]:
        """生成测试数据"""
        data = []
        for i in range(size):
            data.append({
                "shot": 240830000 + i,
                "label": f"test_label_{i % 5}",
                "start_time": i * 0.1,
                "end_time": (i + 1) * 0.1,
                "annotator": i % 3 + 1,
                "annotation_id": 1000 + i
            })
        return data
    
    def _setup_query_test_data(self, table_name: str, db_type: str):
        """设置查询测试数据"""
        # 创建测试表并插入一些数据
        test_data = self._generate_test_data(100)
        DatabaseFactory.insert_annotations(table_name, test_data, db_type=db_type)

def run_performance_benchmark():
    """运行完整的性能测试"""
    print("开始 TOKLABEL 数据库性能对比测试...")
    
    benchmark = PerformanceBenchmark()
    
    # 1. 表创建性能测试
    print("\n1. 表创建性能测试")
    benchmark.benchmark_table_creation(['test_table_1', 'test_table_2'], iterations=3)
    
    # 2. 数据插入性能测试
    print("\n2. 数据插入性能测试")
    benchmark.benchmark_data_insertion('test_insert_table', [100, 500, 1000], iterations=2)
    
    # 3. 数据查询性能测试
    print("\n3. 数据查询性能测试")
    query_scenarios = [
        {'name': '简单查询', 'type': 'simple', 'shots': [240830000, 240830001]},
        {'name': '复杂查询', 'type': 'complex', 'shots': [240830000, 240830001], 'columns': ['shot', 'label']}
    ]
    benchmark.benchmark_data_query('test_query_table', query_scenarios, iterations=2)
    
    # 4. 并发操作性能测试
    print("\n4. 并发操作性能测试")
    benchmark.benchmark_concurrent_operations('test_concurrent_table', [2, 5], operations_per_user=5)
    
    # 生成报告
    print("\n生成性能测试报告...")
    report = benchmark.generate_report()
    
    # 保存报告到文件
    with open('performance_benchmark_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("性能测试完成！报告已保存到 performance_benchmark_report.txt")
    print("\n" + "=" * 80)
    print(report)

if __name__ == '__main__':
    run_performance_benchmark()
