from abc import ABC, abstractmethod
import os
import shutil
from typing import List, Optional
from minio import Minio
from minio.error import S3Error
import tempfile
from io import BytesIO

class StorageAdapter(ABC):
    """存储适配器抽象基类，定义存储操作的通用接口"""
    
    @abstractmethod
    def upload_file(self, file_path: str, content: bytes) -> str:
        """上传文件到存储"""
        pass
    
    @abstractmethod
    def download_file(self, file_path: str) -> bytes:
        """从存储下载文件"""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """删除存储中的文件"""
        pass
    
    @abstractmethod
    def list_files(self, dir_path: str, recursive: bool = False) -> List[str]:
        """列出存储中的文件"""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        pass

class LocalStorageAdapter(StorageAdapter):
    """本地存储适配器，实现本地文件系统存储"""
    
    def __init__(self, base_dir: str):
        """
        初始化本地存储适配器
        
        参数:
        base_dir (str): 本地存储的基础目录
        """
        self.base_dir = base_dir
        
    def upload_file(self, file_path: str, content: bytes) -> str:
        """
        上传文件到本地存储
        
        参数:
        file_path (str): 文件路径
        content (bytes): 文件内容
        
        返回:
        str: 上传的文件路径
        """
        full_path = os.path.join(self.base_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        if os.path.exists(full_path):
            os.remove(full_path)
            
        with open(full_path, "wb") as f:
            f.write(content)
        return file_path
    
    def download_file(self, file_path: str) -> bytes:
        """
        从本地存储下载文件
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bytes: 文件内容
        """
        full_path = os.path.join(self.base_dir, file_path)
        with open(full_path, "rb") as f:
            return f.read()
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除本地存储中的文件
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bool: 删除是否成功
        """
        full_path = os.path.join(self.base_dir, file_path)
        if os.path.isfile(full_path):
            os.remove(full_path)
            return True
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)
            return True
        return False
    
    def list_files(self, dir_path: str, recursive: bool = False) -> List[str]:
        """
        列出本地存储中的文件
        
        参数:
        dir_path (str): 目录路径
        recursive (bool): 是否递归列出子目录
        
        返回:
        List[str]: 文件路径列表
        """
        full_path = os.path.join(self.base_dir, dir_path)
        if not os.path.exists(full_path):
            return []
        
        files = []
        if recursive:
            for root, dirs, filenames in os.walk(full_path):
                for filename in filenames:
                    rel_path = os.path.relpath(os.path.join(root, filename), self.base_dir)
                    files.append(rel_path.replace("\\", "/"))
        else:
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                if os.path.isfile(item_path):
                    rel_path = os.path.relpath(item_path, self.base_dir)
                    files.append(rel_path.replace("\\", "/"))
        return files
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查本地存储中文件是否存在
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bool: 文件是否存在
        """
        full_path = os.path.join(self.base_dir, file_path)
        return os.path.exists(full_path)

class MinIOStorageAdapter(StorageAdapter):
    """MinIO存储适配器，实现MinIO对象存储"""
    
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        """
        初始化MinIO存储适配器
        
        参数:
        endpoint (str): MinIO服务端点
        access_key (str): 访问密钥
        secret_key (str): 秘密密钥
        bucket (str): 存储桶名称
        secure (bool): 是否使用HTTPS
        """
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket = bucket
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保存储桶存在，如果不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            print(f"Error creating bucket: {e}")
    
    def upload_file(self, file_path: str, content: bytes) -> str:
        """
        上传文件到MinIO
        
        参数:
        file_path (str): 文件路径
        content (bytes): 文件内容
        
        返回:
        str: 上传的文件路径
        """
        try:
            self.client.put_object(
                self.bucket,
                file_path,
                BytesIO(content),
                len(content)
            )
            return file_path
        except S3Error as e:
            raise Exception(f"Failed to upload file to MinIO: {e}")
    
    def download_file(self, file_path: str) -> bytes:
        """
        从MinIO下载文件
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bytes: 文件内容
        """
        try:
            response = self.client.get_object(self.bucket, file_path)
            return response.read()
        except S3Error as e:
            raise Exception(f"Failed to download file from MinIO: {e}")
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除MinIO中的文件
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bool: 删除是否成功
        """
        try:
            # 如果是目录，删除所有以该路径为前缀的对象
            if file_path.endswith('/') or not file_path:
                objects = self.client.list_objects(self.bucket, prefix=file_path, recursive=True)
                for obj in objects:
                    self.client.remove_object(self.bucket, obj.object_name)
            else:
                self.client.remove_object(self.bucket, file_path)
            return True
        except S3Error as e:
            print(f"Error deleting file: {e}")
            return False
    
    def list_files(self, dir_path: str, recursive: bool = False) -> List[str]:
        """
        列出MinIO中的文件
        
        参数:
        dir_path (str): 目录路径
        recursive (bool): 是否递归列出
        
        返回:
        List[str]: 文件路径列表
        """
        try:
            prefix = dir_path if dir_path.endswith('/') or not dir_path else dir_path + '/'
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=recursive)
            return [obj.object_name for obj in objects if not obj.object_name.endswith('/')]
        except S3Error as e:
            print(f"Error listing files: {e}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查MinIO中文件是否存在
        
        参数:
        file_path (str): 文件路径
        
        返回:
        bool: 文件是否存在
        """
        try:
            self.client.stat_object(self.bucket, file_path)
            return True
        except S3Error:
            return False
