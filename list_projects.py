#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime

# 尝试导入 label-studio-sdk
try:
    from label_studio_sdk import Client
    print("✅ label-studio-sdk 导入成功")
except ImportError as e:
    print("❌ 错误：无法导入 label-studio-sdk")
    print("请运行以下命令安装：")
    print("pip install label-studio-sdk")
    sys.exit(1)

# 尝试导入项目配置
try:
    from toklabel.config import LABEL_STUDIO_URL, LABEL_STUDIO_API_KEY
    print("✅ 项目配置文件导入成功")
    USE_PROJECT_CONFIG = True
except ImportError:
    print("⚠️  无法导入项目配置，将使用环境变量或默认配置")
    USE_PROJECT_CONFIG = False

class LabelStudioProjectLister:
    """Label Studio 项目列表器"""
    
    def __init__(self):
        """初始化"""
        self.client = None
        self.connection_successful = False
        
    def get_config(self):
        """
        获取配置信息
        优先级：项目配置 > 环境变量 > 默认值
        """
        if USE_PROJECT_CONFIG:
            url = LABEL_STUDIO_URL
            api_key = LABEL_STUDIO_API_KEY
            print(f"📋 使用项目配置：URL={url}")
        else:
            # 从环境变量获取配置
            url = os.environ.get("LABEL_STUDIO_URL", "xxxxxx")
            api_key = os.environ.get("LABEL_STUDIO_API_TOKEN", "xxxxxx")
            print(f"📋 使用环境变量配置：URL={url}")
        
        return {
            "url": url,
            "api_key": api_key
        }
    
    def connect_to_label_studio(self):
        """
        连接到 Label Studio
        
        返回:
        -------
        bool: 连接是否成功
        """
        print("\n" + "="*50)
        print("🔗 连接到 Label Studio")
        print("="*50)
        
        config = self.get_config()
        
        # 检查配置
        if not config["api_key"] or config["api_key"] == "your_api_token_here":
            print("❌ 错误：API Token 未设置")
            print("请设置环境变量 LABEL_STUDIO_API_TOKEN 或在 .env 文件中配置")
            return False
        
        try:
            # 创建客户端
            print(f"🔧 正在连接到: {config['url']}")
            self.client = Client(url=config["url"], api_key=config["api_key"])
            
            # 测试连接
            print("🔍 正在验证连接...")
            self.client.check_connection()
            
            print("✅ 连接成功！")
            self.connection_successful = True
            return True
            
        except Exception as e:
            print(f"❌ 连接失败：{e}")
            return False
    
    def list_all_projects(self):
        """
        列出所有项目
        
        返回:
        -------
        list: 项目列表
        """
        if not self.connection_successful:
            print("❌ 错误：未连接到 Label Studio")
            return []
        
        print("\n" + "="*50)
        print("📋 获取项目列表")
        print("="*50)
        
        try:
            # 获取项目列表
            print("🔍 正在获取项目列表...")
            projects = self.client.get_projects()
            
            print(f"✅ 成功获取项目列表，共有 {len(projects)} 个项目")
            
            if projects:
                print("\n📊 项目详情：")
                print("-" * 80)
                for i, project in enumerate(projects, 1):
                    print(f"项目 #{i}")
                    print(f"  🆔 项目ID: {project['id']}")
                    print(f"  📛 名称: {project['title']}")
                    print(f"  📄 描述: {project.get('description', '无描述')}")
                    print(f"  📅 创建时间: {project.get('created_at', '未知')}")
                    print(f"  📅 更新时间: {project.get('updated_at', '未知')}")
                    print(f"  👤 创建者: {project.get('created_by', {}).get('username', '未知')}")
                    print(f"  🏷️  标签: {project.get('label_config', '无配置')[:100]}..." if project.get('label_config') else "  🏷️  标签: 无配置")
                    print(f"  📊 任务数量: {project.get('task_number', '未知')}")
                    print(f"  ✅ 已完成任务: {project.get('finished_task_number', '未知')}")
                    print(f"  ⏭️  跳过任务: {project.get('skipped_task_number', '未知')}")
                    print(f"  📈 完成率: {project.get('completion_percentage', '未知')}%")
                    print("-" * 80)
            else:
                print("📝 当前没有项目")
            
            return projects
            
        except Exception as e:
            print(f"❌ 获取项目列表失败：{e}")
            
            # 检查是否是Token问题
            if "401" in str(e) or "Unauthorized" in str(e):
                print("💡 这可能是API Token过期或无效的问题")
                print("🔧 解决建议：")
                print("   1. 检查Token是否正确")
                print("   2. 在Label Studio的Account & Settings中重新生成Token")
                print("   3. 确认Token有足够的权限")
            
            return []
    
    def get_project_summary(self, projects):
        """
        获取项目汇总信息
        
        参数:
        -------
        projects: list - 项目列表
        """
        if not projects:
            return
        
        print("\n" + "="*50)
        print("📊 项目汇总统计")
        print("="*50)
        
        total_projects = len(projects)
        total_tasks = sum(project.get('task_number', 0) for project in projects)
        total_finished = sum(project.get('finished_task_number', 0) for project in projects)
        total_skipped = sum(project.get('skipped_task_number', 0) for project in projects)
        
        print(f"📈 总项目数: {total_projects}")
        print(f"📋 总任务数: {total_tasks}")
        print(f"✅ 已完成任务: {total_finished}")
        print(f"⏭️  跳过任务: {total_skipped}")
        
        if total_tasks > 0:
            completion_rate = (total_finished / total_tasks) * 100
            print(f"📊 总体完成率: {completion_rate:.1f}%")
        
        # 按完成率排序
        projects_with_completion = [p for p in projects if p.get('completion_percentage') is not None]
        if projects_with_completion:
            print(f"\n🏆 完成率最高的项目:")
            sorted_projects = sorted(projects_with_completion, 
                                   key=lambda x: x.get('completion_percentage', 0), 
                                   reverse=True)
            for i, project in enumerate(sorted_projects[:3], 1):
                print(f"  {i}. {project['title']} - {project.get('completion_percentage', 0)}%")

def main():
    """主函数"""
    print("🎯 Label Studio 项目列表工具")
    print("=" * 50)
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建项目列表器实例
    lister = LabelStudioProjectLister()
    
    # 连接到 Label Studio
    if not lister.connect_to_label_studio():
        print("\n😞 无法连接到 Label Studio，程序退出")
        sys.exit(1)
    
    # 获取项目列表
    projects = lister.list_all_projects()
    
    # 显示项目汇总
    lister.get_project_summary(projects)
    
    print("\n🎉 项目列表获取完成！")
    
    return len(projects) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
