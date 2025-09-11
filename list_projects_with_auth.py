#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests
import json
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

class LabelStudioProjectLister:
    """Label Studio 项目列表器（支持Personal Access Token认证）"""
    
    def __init__(self):
        """初始化"""
        self.base_url = "xxxxxxxxx"
        self.refresh_token = "xxxxxxxxxxx"
        self.access_token = None
        self.connection_successful = False
        
    def get_access_token(self):
        """
        使用 refresh token 获取 access token
        
        返回:
        -------
        str: access token 或 None
        """
        print("\n" + "="*50)
        print("🔑 获取 Access Token")
        print("="*50)
        
        try:
            # 根据官方文档，使用 refresh token 获取 access token
            url = f"{self.base_url}/api/token/refresh"
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "refresh": self.refresh_token
            }
            
            print(f"🔧 正在请求 access token...")
            print(f"📍 请求URL: {url}")
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get("access")
                print("✅ 成功获取 access token")
                return self.access_token
            else:
                print(f"❌ 获取 access token 失败: HTTP {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 获取 access token 时出错: {e}")
            return None
    
    def test_connection_with_sdk(self):
        """
        使用SDK测试基本连接
        
        返回:
        -------
        bool: 连接是否成功
        """
        print("\n" + "="*50)
        print("🔗 使用SDK测试连接")
        print("="*50)
        
        try:
            # 使用SDK测试基本连接
            ls = Client(url=self.base_url, api_key=self.refresh_token)
            ls.check_connection()
            print("✅ SDK连接成功！")
            self.connection_successful = True
            return True
            
        except Exception as e:
            print(f"❌ SDK连接失败：{e}")
            return False
    
    def list_projects_with_http_api(self):
        """
        使用HTTP API获取项目列表
        
        返回:
        -------
        list: 项目列表
        """
        if not self.access_token:
            print("❌ 错误：没有有效的 access token")
            return []
        
        print("\n" + "="*50)
        print("📋 使用HTTP API获取项目列表")
        print("="*50)
        
        try:
            # 使用HTTP API获取项目列表
            url = f"{self.base_url}/api/projects"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"🔧 正在请求项目列表...")
            print(f"📍 请求URL: {url}")
            print(f"🔑 使用Bearer Token认证")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"📊 API响应数据结构: {list(data.keys())}")
                
                # 检查返回的数据结构
                if 'results' in data:
                    projects = data['results']
                    total_count = data.get('count', len(projects))
                    print(f"✅ 成功获取项目列表，共有 {total_count} 个项目")
                    return projects
                elif isinstance(data, list):
                    print(f"✅ 成功获取项目列表，共有 {len(data)} 个项目")
                    return data
                else:
                    print(f"⚠️  未知的数据格式: {type(data)}")
                    print(f"数据内容: {data}")
                    return []
            else:
                print(f"❌ 获取项目列表失败: HTTP {response.status_code}")
                print(f"响应内容: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ 获取项目列表时出错: {e}")
            return []
    
    def display_projects(self, projects):
        """
        显示项目信息
        
        参数:
        -------
        projects: list - 项目列表
        """
        if not projects:
            print("📝 当前没有项目")
            return
        
        print("\n" + "="*50)
        print("📊 项目详情")
        print("="*50)
        
        # 检查projects是否是列表
        if isinstance(projects, str):
            print(f"⚠️  返回的数据是字符串: {projects}")
            return
        
        for i, project in enumerate(projects, 1):
            print(f"项目 #{i}")
            # 安全地获取项目信息
            if isinstance(project, dict):
                print(f"  🆔 项目ID: {project.get('id', '未知')}")
                print(f"  📛 名称: {project.get('title', '未知')}")
                print(f"  📄 描述: {project.get('description', '无描述')}")
                print(f"  📅 创建时间: {project.get('created_at', '未知')}")
                print(f"  📅 更新时间: {project.get('updated_at', '未知')}")
                print(f"  👤 创建者: {project.get('created_by', {}).get('username', '未知')}")
                print(f"  📊 任务数量: {project.get('task_number', '未知')}")
                print(f"  ✅ 已完成任务: {project.get('finished_task_number', '未知')}")
                print(f"  ⏭️  跳过任务: {project.get('skipped_task_number', '未知')}")
                print(f"  📈 完成率: {project.get('completion_percentage', '未知')}%")
            else:
                print(f"  ⚠️  项目数据格式异常: {type(project)} - {project}")
            print("-" * 60)
    
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
        
        # 过滤出有效的项目数据
        valid_projects = [p for p in projects if isinstance(p, dict)]
        
        total_projects = len(valid_projects)
        total_tasks = sum(project.get('task_number', 0) for project in valid_projects)
        total_finished = sum(project.get('finished_task_number', 0) for project in valid_projects)
        total_skipped = sum(project.get('skipped_task_number', 0) for project in valid_projects)
        
        print(f"📈 总项目数: {total_projects}")
        print(f"📋 总任务数: {total_tasks}")
        print(f"✅ 已完成任务: {total_finished}")
        print(f"⏭️  跳过任务: {total_skipped}")
        
        if total_tasks > 0:
            completion_rate = (total_finished / total_tasks) * 100
            print(f"📊 总体完成率: {completion_rate:.1f}%")

def main():
    """主函数"""
    print("🎯 Label Studio 项目列表工具（支持Personal Access Token）")
    print("=" * 60)
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建项目列表器实例
    lister = LabelStudioProjectLister()
    
    # 步骤1: 使用SDK测试基本连接
    if not lister.test_connection_with_sdk():
        print("\n😞 SDK连接失败，程序退出")
        sys.exit(1)
    
    # 步骤2: 获取access token
    if not lister.get_access_token():
        print("\n😞 无法获取access token，程序退出")
        sys.exit(1)
    
    # 步骤3: 使用HTTP API获取项目列表
    projects = lister.list_projects_with_http_api()
    
    # 步骤4: 显示项目信息
    lister.display_projects(projects)
    
    # 步骤5: 显示项目汇总
    lister.get_project_summary(projects)
    
    print("\n🎉 项目列表获取完成！")
    
    return len(projects) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
