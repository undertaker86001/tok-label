"""
音频标注项目创建脚本

使用ProjectBuilder创建音频标注项目
"""

import toklabel
from toklabel import ProjectBuilder
import json
import os


def create_audio_annotation_project():
    """创建音频标注项目"""
    
    print("🎵 创建音频标注项目...")
    
    # 连接Label Studio
    API_KEY = os.getenv('LABEL_STUDIO_API_KEY', 'your_api_key_here')
    if API_KEY == 'your_api_key_here':
        print("⚠️  请设置环境变量 LABEL_STUDIO_API_KEY")
        return None
    
    try:
        ls = toklabel.connect_Label_Studio(API_key=API_KEY)
        print("✅ 成功连接到Label Studio")
    except Exception as e:
        print(f"❌ 连接Label Studio失败: {str(e)}")
        return None
    
    # 使用ProjectBuilder创建项目
    config_file = 'audio_annotation.yaml'
    if not os.path.exists(config_file):
        print(f"❌ 配置文件 {config_file} 不存在")
        return None
    
    try:
        pb = ProjectBuilder(config_file)
        print("✅ ProjectBuilder初始化成功")
    except Exception as e:
        print(f"❌ ProjectBuilder初始化失败: {str(e)}")
        return None
    
    try:
        # 准备数据
        print("📊 准备音频数据...")
        urls = pb.prepare_data()
        print(f"✅ 数据准备完成，生成了 {len(urls)} 个数据文件")
        
        # 创建项目
        print("🏗️  创建Label Studio项目...")
        proj = pb.create_project(ls)
        print(f"✅ 项目创建成功，项目ID: {proj.id}")
        
        # 创建存储并同步
        print("💾 创建存储...")
        storage = pb.create_storage(ls)
        print(f"✅ 存储创建成功: {storage}")
        
        print("\n🎉 音频标注项目设置完成！")
        print(f"项目ID: {proj.id}")
        print(f"项目名称: {proj.title}")
        print(f"存储ID: {storage.id}")
        
        return proj, storage
        
    except Exception as e:
        print(f"❌ 项目创建失败: {str(e)}")
        return None


def main():
    """主函数"""
    print("=" * 50)
    print("🎵 TOKLABEL 音频标注项目创建器")
    print("=" * 50)
    
    # 检查环境
    print("🔍 检查环境...")
    if not os.path.exists('audio_annotation.yaml'):
        print("❌ 配置文件 audio_annotation.yaml 不存在")
        print("请确保在正确的目录中运行此脚本")
        return
    
    # 创建项目
    result = create_audio_annotation_project()
    
    if result:
        proj, storage = result
        print("\n📋 下一步操作:")
        print("1. 在Label Studio中查看项目")
        print("2. 上传音频文件")
        print("3. 开始标注任务")
        print("4. 使用ML Backend进行预标注")
        
        # 保存项目信息
        project_info = {
            'project_id': proj.id,
            'project_title': proj.title,
            'storage_id': storage.id,
            'created_at': proj.created_at.isoformat() if hasattr(proj, 'created_at') else None
        }
        
        with open('audio_project_info.json', 'w', encoding='utf-8') as f:
            json.dump(project_info, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 项目信息已保存到 audio_project_info.json")
    else:
        print("\n❌ 项目创建失败，请检查错误信息")


if __name__ == "__main__":
    main()
