#!/usr/bin/env python3
"""
公司MinIO Bucket创建脚本
使用公司MinIO信息创建新的bucket，不影响现有bucket
"""

import os
import sys
from minio import Minio
from minio.error import S3Error
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompanyMinIOManager:
    """公司MinIO管理器"""
    
    def __init__(self):
        """初始化MinIO客户端"""
        # 公司MinIO配置
        self.endpoint = "192.168.32.4:30118"
        self.access_key = "admin"
        self.secret_key = "U#tV6jhcLAP!xK3d"
        self.secure = False  # 使用HTTP
        
        # 初始化MinIO客户端
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            logger.info("MinIO客户端初始化成功")
        except Exception as e:
            logger.error(f"MinIO客户端初始化失败: {e}")
            raise
    
    def list_existing_buckets(self):
        """列出现有的所有bucket"""
        try:
            buckets = list(self.client.list_buckets())
            logger.info(f"找到 {len(buckets)} 个现有bucket:")
            
            for bucket in buckets:
                logger.info(f"  - {bucket.name} (创建时间: {bucket.creation_date})")
            
            return [bucket.name for bucket in buckets]
        except Exception as e:
            logger.error(f"列出bucket失败: {e}")
            return []
    
    def create_new_bucket(self, bucket_name: str, region: str = "us-east-1"):
        """
        创建新的bucket
        
        Args:
            bucket_name: bucket名称
            region: 区域
            
        Returns:
            是否成功
        """
        try:
            # 检查bucket是否已存在
            if self.client.bucket_exists(bucket_name):
                logger.warning(f"Bucket '{bucket_name}' 已存在")
                return False
            
            # 创建新bucket
            self.client.make_bucket(bucket_name, location=region)
            logger.info(f"成功创建bucket: {bucket_name}")
            
            # 验证bucket创建成功
            if self.client.bucket_exists(bucket_name):
                logger.info(f"Bucket '{bucket_name}' 创建验证成功")
                return True
            else:
                logger.error(f"Bucket '{bucket_name}' 创建验证失败")
                return False
                
        except S3Error as e:
            logger.error(f"创建bucket失败 (S3Error): {e}")
            return False
        except Exception as e:
            logger.error(f"创建bucket失败: {e}")
            return False
    
    def set_bucket_policy(self, bucket_name: str, policy: str):
        """
        设置bucket策略
        
        Args:
            bucket_name: bucket名称
            policy: 策略JSON字符串
        """
        try:
            self.client.set_bucket_policy(bucket_name, policy)
            logger.info(f"成功设置bucket '{bucket_name}' 的策略")
        except Exception as e:
            logger.error(f"设置bucket策略失败: {e}")
    
    def create_folder_structure(self, bucket_name: str, folders: list):
        """
        在bucket中创建文件夹结构
        
        Args:
            bucket_name: bucket名称
            folders: 文件夹列表
        """
        try:
            for folder in folders:
                # 创建空对象作为文件夹标记
                folder_path = f"{folder}/"
                self.client.put_object(bucket_name, folder_path, "", 0)
                logger.info(f"创建文件夹: {folder_path}")
        except Exception as e:
            logger.error(f"创建文件夹结构失败: {e}")
    
    def test_bucket_access(self, bucket_name: str):
        """
        测试bucket访问权限
        
        Args:
            bucket_name: bucket名称
        """
        try:
            # 尝试上传测试文件
            test_content = "test file content"
            test_object_name = "test/test.txt"
            
            self.client.put_object(
                bucket_name, 
                test_object_name, 
                test_content.encode('utf-8'), 
                len(test_content)
            )
            logger.info(f"测试文件上传成功: {test_object_name}")
            
            # 尝试下载测试文件
            response = self.client.get_object(bucket_name, test_object_name)
            downloaded_content = response.read().decode('utf-8')
            response.close()
            response.release_conn()
            
            if downloaded_content == test_content:
                logger.info("测试文件下载成功，内容验证通过")
            else:
                logger.warning("测试文件内容验证失败")
            
            # 清理测试文件
            self.client.remove_object(bucket_name, test_object_name)
            logger.info("测试文件清理完成")
            
            return True
            
        except Exception as e:
            logger.error(f"测试bucket访问失败: {e}")
            return False

def main():
    """主函数"""
    print("=== 公司MinIO Bucket创建工具 ===")
    
    # 创建MinIO管理器
    try:
        minio_manager = CompanyMinIOManager()
    except Exception as e:
        print(f"连接MinIO失败: {e}")
        return
    
    # 列出现有bucket
    print("\n1. 列出现有bucket:")
    existing_buckets = minio_manager.list_existing_buckets()
    
    # 建议的bucket名称
    suggested_bucket_name = "toklabel-audio-storage"
    
    print(f"\n2. 建议创建的新bucket名称: {suggested_bucket_name}")
    
    # 检查建议的bucket是否已存在
    if suggested_bucket_name in existing_buckets:
        print(f"⚠️  Bucket '{suggested_bucket_name}' 已存在")
        # 生成新的bucket名称
        import time
        timestamp = int(time.time())
        suggested_bucket_name = f"toklabel-audio-storage-{timestamp}"
        print(f"   使用新的bucket名称: {suggested_bucket_name}")
    
    # 创建新bucket
    print(f"\n3. 创建新bucket: {suggested_bucket_name}")
    if minio_manager.create_new_bucket(suggested_bucket_name):
        print(f"✅ Bucket '{suggested_bucket_name}' 创建成功")
        
        # 创建文件夹结构
        print("\n4. 创建文件夹结构:")
        folders = [
            "audio-files",
            "meta-files", 
            "processed-audio",
            "annotations",
            "exports",
            "temp"
        ]
        
        minio_manager.create_folder_structure(suggested_bucket_name, folders)
        
        # 设置bucket策略（可选）
        print("\n5. 设置bucket访问策略:")
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": [
                        "s3:GetBucketLocation",
                        "s3:ListBucket"
                    ],
                    "Resource": f"arn:aws:s3:::{suggested_bucket_name}"
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": [
                        "s3:GetObject"
                    ],
                    "Resource": f"arn:aws:s3:::{suggested_bucket_name}/*"
                }
            ]
        }
        
        try:
            minio_manager.set_bucket_policy(suggested_bucket_name, str(policy))
            print("✅ Bucket策略设置成功")
        except Exception as e:
            print(f"⚠️  Bucket策略设置失败: {e}")
        
        # 测试bucket访问
        print("\n6. 测试bucket访问:")
        if minio_manager.test_bucket_access(suggested_bucket_name):
            print("✅ Bucket访问测试通过")
        else:
            print("❌ Bucket访问测试失败")
        
        # 显示最终信息
        print(f"\n=== 创建完成 ===")
        print(f"Bucket名称: {suggested_bucket_name}")
        print(f"MinIO地址: http://{minio_manager.endpoint}")
        print(f"访问密钥: {minio_manager.access_key}")
        print(f"文件夹结构:")
        for folder in folders:
            print(f"  - {folder}/")
        
        # 保存配置信息
        config_info = {
            "bucket_name": suggested_bucket_name,
            "endpoint": minio_manager.endpoint,
            "access_key": minio_manager.access_key,
            "secret_key": minio_manager.secret_key,
            "secure": minio_manager.secure,
            "folders": folders,
            "created_at": "2024-01-15T12:00:00Z"
        }
        
        with open("company_minio_config.json", "w", encoding="utf-8") as f:
            import json
            json.dump(config_info, f, indent=2, ensure_ascii=False)
        
        print(f"\n配置信息已保存到: company_minio_config.json")
        
    else:
        print(f"❌ Bucket '{suggested_bucket_name}' 创建失败")
    
    # 再次列出所有bucket确认
    print(f"\n7. 确认bucket列表:")
    final_buckets = minio_manager.list_existing_buckets()
    if suggested_bucket_name in final_buckets:
        print(f"✅ 新bucket '{suggested_bucket_name}' 已成功添加到bucket列表中")

if __name__ == "__main__":
    main()
