#!/usr/bin/env python3
"""
MinIO集成命令行工具
"""

import click
import json
import sys
from pathlib import Path

@click.group()
def cli():
    """MinIO集成命令行工具"""
    pass

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--bucket', default='tok-label', help='MinIO存储桶')
@click.option('--prefix', default='', help='对象前缀')
@click.option('--auto-sync', is_flag=True, help='启用自动同步')
def enable(config, bucket, prefix, auto_sync):
    """启用MinIO集成"""
    from toklabel.minio_config_manager import MinIOConfigManager
    
    config_manager = MinIOConfigManager(config)
    result = config_manager.enable_minio(
        bucket=bucket,
        prefix=prefix,
        auto_sync=auto_sync
    )
    
    if result.get("error"):
        click.echo(f"错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
def disable(config):
    """禁用MinIO集成"""
    from toklabel.minio_config_manager import MinIOConfigManager
    
    config_manager = MinIOConfigManager(config)
    result = config_manager.disable_minio()
    
    if result.get("error"):
        click.echo(f"错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--prefix', default='', help='MinIO对象前缀')
@click.option('--force', is_flag=True, help='强制重新导入')
def import_data(config, prefix, force):
    """从MinIO导入数据"""
    from toklabel.minio_workflow_manager import MinIOWorkflowManager
    
    workflow = MinIOWorkflowManager(config)
    init_result = workflow.initialize_project()
    
    if init_result.get("error"):
        click.echo(f"初始化错误: {init_result['error']}", err=True)
        sys.exit(1)
    
    result = workflow.project_builder.import_from_minio(
        minio_prefix=prefix,
        force_reload=force
    )
    
    if result.get("error"):
        click.echo(f"导入错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")
        if result.get("imported_shots"):
            click.echo(f"导入的炮号: {result['imported_shots']}")

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--prefix', default='', help='MinIO对象前缀')
@click.option('--include-annotations', is_flag=True, help='包含标注数据')
def export_data(config, prefix, include_annotations):
    """导出数据到MinIO"""
    from toklabel.minio_workflow_manager import MinIOWorkflowManager
    
    workflow = MinIOWorkflowManager(config)
    init_result = workflow.initialize_project()
    
    if init_result.get("error"):
        click.echo(f"初始化错误: {init_result['error']}", err=True)
        sys.exit(1)
    
    result = workflow.project_builder.export_to_minio(
        minio_prefix=prefix,
        include_annotations=include_annotations
    )
    
    if result.get("error"):
        click.echo(f"导出错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")
        click.echo(f"上传文件数: {len(result.get('uploaded_files', []))}")

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--pipeline-index', default=0, help='管道索引')
def run_pipeline(config, pipeline_index):
    """运行数据处理管道"""
    from toklabel.minio_workflow_manager import MinIOWorkflowManager
    
    workflow = MinIOWorkflowManager(config)
    init_result = workflow.initialize_project()
    
    if init_result.get("error"):
        click.echo(f"初始化错误: {init_result['error']}", err=True)
        sys.exit(1)
    
    result = workflow.run_data_pipeline(pipeline_index)
    
    if result.get("error"):
        click.echo(f"管道执行错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")

@cli.command()
@click.option('--bucket', default='tok-label', help='MinIO存储桶')
def health_check(bucket):
    """MinIO健康检查"""
    from toklabel.minio_monitor import MinIOMonitor
    
    monitor = MinIOMonitor(bucket)
    result = monitor.health_check()
    
    if result["status"] == "error":
        click.echo(f"✗ {result['message']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ MinIO健康状态: {result['status']}")
        click.echo(f"端点: {result['endpoint']}")
        click.echo(f"存储桶存在: {result['bucket_exists']}")

@cli.command()
@click.option('--bucket', default='tok-label', help='MinIO存储桶')
@click.option('--prefix', default='', help='对象前缀')
def stats(bucket, prefix):
    """获取MinIO存储统计信息"""
    from toklabel.minio_monitor import MinIOMonitor
    
    monitor = MinIOMonitor(bucket)
    result = monitor.get_storage_statistics(prefix)
    
    if result.get("error"):
        click.echo(f"统计错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"总对象数: {result['total_objects']}")
        click.echo(f"总大小: {result['total_size_mb']} MB")
        click.echo(f"文件类型分布: {json.dumps(result['file_types'], indent=2, ensure_ascii=False)}")

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--prefix', default='', help='验证前缀')
@click.option('--required-columns', help='必需列名（逗号分隔）')
def validate(config, prefix, required_columns):
    """验证MinIO中的数据文件"""
    from toklabel.minio_workflow_manager import MinIOWorkflowManager
    from toklabel.minio_validator import MinIODataValidator
    
    workflow = MinIOWorkflowManager(config)
    init_result = workflow.initialize_project()
    
    if init_result.get("error"):
        click.echo(f"初始化错误: {init_result['error']}", err=True)
        sys.exit(1)
    
    validator = MinIODataValidator(workflow.project_builder.project)
    
    columns = required_columns.split(',') if required_columns else None
    result = validator.validate_csv_files(prefix=prefix, required_columns=columns)
    
    if result.get("error"):
        click.echo(f"验证错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")
        click.echo(f"有效文件: {result['valid_files']}")
        click.echo(f"无效文件: {result['invalid_files']}")

@cli.command()
@click.option('--local-dir', help='本地数据目录')
@click.option('--project', help='项目名称')
@click.option('--bucket', default='tok-label', help='MinIO存储桶')
@click.option('--prefix', default='', help='对象前缀')
@click.option('--mode', type=click.Choice(['local', 'redis', 'both']), default='both', help='迁移模式')
def migrate(local_dir, project, bucket, prefix, mode):
    """迁移数据到MinIO"""
    import subprocess
    
    cmd = ['python', 'scripts/migrate_to_minio.py']
    cmd.extend(['--bucket', bucket, '--prefix', prefix, '--mode', mode])
    
    if local_dir:
        cmd.extend(['--local-dir', local_dir])
    if project:
        cmd.extend(['--project', project])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        click.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        click.echo(f"迁移失败: {e.stderr}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--config', default='project-config.yaml', help='配置文件路径')
@click.option('--direction', type=click.Choice(['import', 'export', 'both']), default='both', help='同步方向')
def sync(config, direction):
    """双向数据同步"""
    from toklabel.minio_workflow_manager import MinIOWorkflowManager
    
    workflow = MinIOWorkflowManager(config)
    init_result = workflow.initialize_project()
    
    if init_result.get("error"):
        click.echo(f"初始化错误: {init_result['error']}", err=True)
        sys.exit(1)
    
    result = workflow.sync_data_bidirectional(direction)
    
    if result.get("error"):
        click.echo(f"同步错误: {result['error']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"✓ {result['message']}")

if __name__ == '__main__':
    cli()
