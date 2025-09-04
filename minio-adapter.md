
第一阶段实现：扩展文件服务器支持MinIO

1. 修改配置文件

首先需要在 toklabel/config.py 中添加MinIO配置： [1](#1-0) 

# 在现有配置基础上添加MinIO配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "tok-label")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # "local" or "minio"

2. 创建MinIO存储适配器

创建新文件 file-server/storage_adapter.py：

from abc import ABC, abstractmethod
import os
import shutil
from typing import List, Optional
from minio import Minio
from minio.error import S3Error
import tempfile
from io import BytesIO

class StorageAdapter(ABC):
    @abstractmethod
    def upload_file(self, file_path: str, content: bytes) -> str:
        pass
    
    @abstractmethod
    def download_file(self, file_path: str) -> bytes:
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        pass
    
    @abstractmethod
    def list_files(self, dir_path: str, recursive: bool = False) -> List[str]:
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        pass

class LocalStorageAdapter(StorageAdapter):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        
    def upload_file(self, file_path: str, content: bytes) -> str:
        full_path = os.path.join(self.base_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        if os.path.exists(full_path):
            os.remove(full_path)
            
        with open(full_path, "wb") as f:
            f.write(content)
        return file_path
    
    def download_file(self, file_path: str) -> bytes:
        full_path = os.path.join(self.base_dir, file_path)
        with open(full_path, "rb") as f:
            return f.read()
    
    def delete_file(self, file_path: str) -> bool:
        full_path = os.path.join(self.base_dir, file_path)
        if os.path.isfile(full_path):
            os.remove(full_path)
            return True
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)
            return True
        return False
    
    def list_files(self, dir_path: str, recursive: bool = False) -> List[str]:
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
        full_path = os.path.join(self.base_dir, file_path)
        return os.path.exists(full_path)

class MinIOStorageAdapter(StorageAdapter):
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket = bucket
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            print(f"Error creating bucket: {e}")
    
    def upload_file(self, file_path: str, content: bytes) -> str:
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
        try:
            response = self.client.get_object(self.bucket, file_path)
            return response.read()
        except S3Error as e:
            raise Exception(f"Failed to download file from MinIO: {e}")
    
    def delete_file(self, file_path: str) -> bool:
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
        try:
            prefix = dir_path if dir_path.endswith('/') or not dir_path else dir_path + '/'
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=recursive)
            return [obj.object_name for obj in objects if not obj.object_name.endswith('/')]
        except S3Error as e:
            print(f"Error listing files: {e}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        try:
            self.client.stat_object(self.bucket, file_path)
            return True
        except S3Error:
            return False

3. 修改文件服务器主文件

修改 file-server/main.py：

from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from typing import Optional
from pydantic import BaseModel
from util import export_postgres_data
import numpy as np
from storage_adapter import StorageAdapter, LocalStorageAdapter, MinIOStorageAdapter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置存储后端
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
DATA_DIR = "/data"
URL_PREFIX = "/files"

# 初始化存储适配器
if STORAGE_BACKEND == "minio":
    storage = MinIOStorageAdapter(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket=os.getenv("MINIO_BUCKET", "tok-label"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
else:
    storage = LocalStorageAdapter(DATA_DIR)
    # 只有本地存储需要挂载静态文件
    app.mount(URL_PREFIX, StaticFiles(directory=DATA_DIR, html=True), name="files")

# 文件下载端点（用于MinIO）
@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    if STORAGE_BACKEND == "minio":
        try:
            content = storage.download_file(file_path)
            from fastapi.responses import Response
            return Response(content=content, media_type="application/octet-stream")
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "Download endpoint only available for MinIO backend"}

# 列出文件
@app.get("/list/")
async def list_files(dir: str = None, recursive: bool = False):
    try:
        if dir is None:
            dir = ""
        
        files = storage.list_files(dir, recursive)
        
        # 根据存储后端生成不同的URL
        if STORAGE_BACKEND == "minio":
            urls = [f"/download/{file}" for file in files]
        else:
            urls = [f"{URL_PREFIX}/{file}" for file in files]
        
        return {"urls": urls, "files": files}
    except Exception as e:
        return {"error": str(e)}

# 删除文件
@app.delete("/delete/")
async def delete_file(dir: str, file: Optional[str] = None):
    try:
        if file is None:
            # 删除整个目录
            target_path = dir
        else:
            # 删除特定文件
            target_path = f"{dir}/{file}" if dir else file
        
        success = storage.delete_file(target_path)
        if success:
            if file is None:
                return {"message": f"Directory {dir} and all contents deleted successfully"}
            else:
                return {"message": f"File {file} deleted successfully"}
        else:
            return {"error": "Failed to delete file/directory"}
    except Exception as e:
        return {"error": str(e)}

# 上传文件
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        file_path = storage.upload_file(file.filename, content)
        
        # 根据存储后端生成不同的URL
        if STORAGE_BACKEND == "minio":
            url = f"/download/{file_path}"
        else:
            url = f"{URL_PREFIX}/{file_path}"
        
        return {
            "message": f"File {file.filename} uploaded successfully",
            "url": url
        }
    except Exception as e:
        return {"error": str(e)}

# 导出数据
class ExportRequest(BaseModel):
    project_name: str
    shots: int | list[int]
    name_table_columns: dict
    t_min: float = -np.inf
    t_max: float = np.inf
    resolution: float = 1e-3

@app.post("/export/")
async def export_pgdata(request: ExportRequest):
    try:
        if isinstance(request.shots, int):
            request.shots = [request.shots]
        
        # 从postgres获取数据
        data = export_postgres_data(
            request.shots, 
            request.name_table_columns, 
            request.t_min, 
            request.t_max, 
            request.resolution
        )
        
        # 保存数据到存储后端
        urls = []
        for shot in request.shots:
            file_name = f"{request.project_name}/{shot}.csv"
            csv_content = data[shot].to_csv(index=False, encoding='utf-8').encode('utf-8')
            
            storage.upload_file(file_name, csv_content)
            
            # 根据存储后端生成不同的URL
            if STORAGE_BACKEND == "minio":
                url = f"/download/{file_name}"
            else:
                url = f"{URL_PREFIX}/{file_name}"
            urls.append(url)
        
        return {
            "message": "Data exported successfully",
            "urls": urls
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

4. 修改工具函数

修改 toklabel/utils.py 中的相关函数以支持MinIO： [3](#1-2) 

# 在现有导入基础上添加
from .config import FILE_SERVER_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE, STORAGE_BACKEND

def get_file_url_prefix():
    """根据存储后端返回正确的URL前缀"""
    if STORAGE_BACKEND == "minio":
        return f"{FILE_SERVER_URL}/download"
    else:
        return f"{FILE_SERVER_URL}/files"

def list_files(dir: str, recursive: bool = False):
    """
    列出目录下的所有文件，支持MinIO和本地存储
    """
    try:
        params = {"dir": dir, "recursive": recursive} 
        response = requests.get(f"{FILE_SERVER_URL}/list/", params=params)
        response.raise_for_status()
        result = response.json()
        
        # URL已经在服务器端正确生成，直接添加服务器前缀
        if "urls" in result:
            result["urls"] = [f"{FILE_SERVER_URL}{url}" for url in result["urls"]]
        return result
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def upload_dataframe(dir: str, file: str, dataframe: pd.DataFrame):
    """
    上传数据框到文件服务器，支持MinIO和本地存储
    
    参数:
    dir (str): 目录路径
    file (str): 文件名，建议以shot_id.csv的格式命名
    dataframe (pd.DataFrame): 数据框
    
    返回:
    message: 操作成功或失败的消息
    """
    try:
        # Convert DataFrame to in-memory CSV file
        csv_buffer = BytesIO()
        dataframe.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_buffer.seek(0)  # Reset buffer position to beginning
        
        # Upload directly
        file_path = f"{dir}/{file}"
        response = requests.post(
            f"{FILE_SERVER_URL}/upload/",
            files={"file": (file_path, csv_buffer, "text/csv")}
        ) 
        response.raise_for_status()
        
        # return url
        result = response.json()
        if "url" in result:
            result["url"] = f"{FILE_SERVER_URL}{result['url']}"
        return result
    except Exception as e:
        return {"error": str(e)}

5. 添加MinIO专用工具函数

在 toklabel/utils.py 中添加以下MinIO专用函数：

def upload_to_minio(file_path: str, content: bytes, bucket: str = None):
    """
    直接上传数据到MinIO
    
    参数:
    file_path (str): MinIO中的文件路径
    content (bytes): 文件内容
    bucket (str, optional): 存储桶名称，默认使用配置中的桶
    
    返回:
    Dict: 包含操作结果的字典
    """
    try:
        from minio import Minio
        from minio.error import S3Error
        
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        bucket_name = bucket or MINIO_BUCKET
        
        # 确保存储桶存在
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        # 上传文件
        client.put_object(
            bucket_name,
            file_path,
            BytesIO(content),
            len(content)
        )
        
        return {
            "message": f"File {file_path} uploaded to MinIO successfully",
            "path": file_path,
            "bucket": bucket_name
        }
    except S3Error as e:
        return {"error": f"MinIO error: {str(e)}"}
    except Exception as e:
        return {"error": f"Upload error: {str(e)}"}

def download_from_minio(file_path: str, bucket: str = None) -> bytes:
    """
    从MinIO下载文件
    
    参数:
    file_path (str): MinIO中的文件路径
    bucket (str, optional): 存储桶名称，默认使用配置中的桶
    
    返回:
    bytes: 文件内容
    """
    try:
        from minio import Minio
        from minio.error import S3Error
        
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        bucket_name = bucket or MINIO_BUCKET
        response = client.get_object(bucket_name, file_path)
        return response.read()
    except S3Error as e:
        raise Exception(f"MinIO error: {str(e)}")
    except Exception as e:
        raise Exception(f"Download error: {str(e)}")

def list_minio_objects(prefix: str = "", bucket: str = None, recursive: bool = False) -> List[str]:
    """
    列出MinIO中的对象
    
    参数:
    prefix (str): 对象前缀
    bucket (str, optional): 存储桶名称，默认使用配置中的桶
    recursive (bool): 是否递归列出
    
    返回:
    List[str]: 对象名称列表
    """
    try:
        from minio import Minio
        from minio.error import S3Error
        
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        bucket_name = bucket or MINIO_BUCKET
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=recursive)
        return [obj.object_name for obj in objects if not obj.object_name.endswith('/')]
    except S3Error as e:
        print(f"MinIO error: {e}")
        return []
    except Exception as e:
        print(f"List error: {e}")
        return []

def import_from_minio_to_redis(
    project_name: str,
    minio_prefix: str = "",
    bucket: str = None,
    key: str = "csv",
    db: int = None
):
    """
    从MinIO导入数据到Redis
    
    参数:
    project_name (str): 项目名称
    minio_prefix (str): MinIO对象前缀
    bucket (str, optional): 存储桶名称
    key (str): Redis中的数据键名
    db (int, optional): Redis数据库编号
    
    返回:
    Dict: 包含操作结果的字典
    """
    try:
        # 列出MinIO中的文件
        files = list_minio_objects(prefix=minio_prefix, bucket=bucket, recursive=True)
        
        if not files:
            return {"error": "No files found in MinIO with the specified prefix"}
        
        # 为每个文件生成下载URL
        urls = {}
        for file_path in files:
            # 从文件路径中提取shot号
            import re
            shot_match = re.search(r'/(\d+)\.csv$', file_path)
            if shot_match:
                shot = int(shot_match.group(1))
                # 生成下载URL
                if STORAGE_BACKEND == "minio":
                    urls[shot] = f"{FILE_SERVER_URL}/download/{file_path}"
                else:
                    # 如果当前不是MinIO模式，需要先下载到本地
                    content = download_from_minio(file_path, bucket)
                    # 上传到本地文件服务器
                    upload_response = requests.post(
                        f"{FILE_SERVER_URL}/upload/",
                        files={"file": (file_path, BytesIO(content), "text/csv")}
                    )
                    if upload_response.status_code == 200:
                        result = upload_response.json()
                        urls[shot] = f"{FILE_SERVER_URL}{result['url']}"
        
        # 导出到Redis
        if urls:
            redis_result = export_urls_to_redis(
                project_name=project_name,
                urls=urls,
                key=key,
                db=db or REDIS_DB
            )
            return {
                "message": f"Successfully imported {len(urls)} files from MinIO to Redis",
                "files_imported": len(urls),
                "redis_result": redis_result
            }
        else:
            return {"error": "No valid CSV files found with shot numbers"}
            
    except Exception as e:
        return {"error": f"Import error: {str(e)}"}

6. 创建MinIO数据导入器类

创建新文件 toklabel/minio_importer.py：

import pandas as pd
from typing import List, Dict, Optional
from .utils import (
    download_from_minio, 
    list_minio_objects, 
    upload_dataframe, 
    export_urls_to_redis,
    connect_redis
)
from .config import MINIO_BUCKET, REDIS_DB
import json
import re
import logging

logger = logging.getLogger(__name__)

class MinIOImporter:
    """MinIO数据导入器，支持从MinIO批量导入数据到Label Studio"""
    
    def __init__(self, project_name: str, bucket: str = None):
        self.project_name = project_name
        self.bucket = bucket or MINIO_BUCKET
    
    def list_available_files(self, prefix: str = "") -> List[str]:
        """列出MinIO中可用的文件"""
        return list_minio_objects(prefix=prefix, bucket=self.bucket, recursive=True)
    
    def download_and_convert_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """从MinIO下载CSV文件并转换为DataFrame"""
        try:
            content = download_from_minio(file_path, self.bucket)
            from io import StringIO
            csv_string = content.decode('utf-8')
            df = pd.read_csv(StringIO(csv_string))
            return df
        except Exception as e:
            logger.error(f"Error downloading/converting {file_path}: {e}")
            return None
    
    def batch_import_csv_files(self, prefix: str = "", shot_pattern: str = r'/(\d+)\.csv$') -> Dict:
        """
        批量导入CSV文件到文件服务器和Redis
        
        参数:
        prefix (str): MinIO对象前缀
        shot_pattern (str): 用于提取shot号的正则表达式
        
        返回:
        Dict: 导入结果
        """
        try:
            # 列出所有CSV文件
            files = self.list_available_files(prefix)
            csv_files = [f for f in files if f.endswith('.csv')]
            
            if not csv_files:
                return {"error": "No CSV files found in MinIO"}
            
            urls = {}
            failed_files = []
            
            for file_path in csv_files:
                # 提取shot号
                shot_match = re.search(shot_pattern, file_path)
                if not shot_match:
                    logger.warning(f"Could not extract shot number from {file_path}")
                    continue
                
                shot = int(shot_match.group(1))
                
                # 下载并转换文件
                df = self.download_and_convert_csv(file_path)
                if df is None:
                    failed_files.append(file_path)
                    continue
                
                # 上传到文件服务器
                upload_result = upload_dataframe(
                    dir=self.project_name,
                    file=f"{shot}.csv",
                    dataframe=df
                )
                
                if upload_result.get("error"):
                    logger.error(f"Failed to upload {file_path}: {upload_result['error']}")
                    failed_files.append(file_path)
                    continue
                
                urls[shot] = upload_result["url"]
            
            # 导出到Redis
            if urls:
                redis_result = export_urls_to_redis(
                    project_name=self.project_name,
                    urls=urls,
                    key="csv",
                    db=REDIS_DB
                )
                
                return {
                    "message": f"Successfully imported {len(urls)} files from MinIO",
                    "imported_shots": list(urls.keys()),
                    "failed_files": failed_files,
                    "redis_result": redis_result
                }
            else:
                return {"error": "No files were successfully imported"}
                
        except Exception as e:
            return {"error": f"Batch import error: {str(e)}"}
    
    def import_json_annotations(self, prefix: str = "annotations/") -> Dict:
        """
        导入JSON格式的标注数据
        
        参数:
        prefix (str): JSON文件的MinIO前缀
        
        返回:
        Dict: 导入结果
        """
        try:
            files = self.list_available_files(prefix)
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                return {"error": "No JSON files found in MinIO"}
            
            redis_conn = connect_redis(REDIS_DB)
            imported_count = 0
            
            for file_path in json_files:
                try:
                    content = download_from_minio(file_path, self.bucket)
                    json_data = json.loads(content.decode('utf-8'))
                    
                    # 提取文件名作为Redis键
                    file_name = file_path.split('/')[-1].replace('.json', '')
                    redis_key = f"{self.project_name}/annotations/{file_name}"
                    
                    redis_conn.set(redis_key, json.dumps(json_data))
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing {file_path}: {e}")
            
            redis_conn.close()
            
            return {
                "message": f"Successfully imported {imported_count} JSON annotation files",
                "imported_count": imported_count,
                "total_files": len(json_files)
            }
            
        except Exception as e:
            return {"error": f"JSON import error: {str(e)}"}

7. 更新 toklabel/config.py

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Label Studio configuration
LABEL_STUDIO_URL = os.getenv('LABEL_STUDIO_URL', 'http://example.com:8080')
LABEL_STUDIO_API_KEY = os.getenv('LABEL_STUDIO_API_KEY')

# File server configuration
FILE_SERVER_URL = os.getenv('FILE_SERVER_URL', 'http://example.com:8000')

# Extractor server configuration
EXTRACTOR_SERVER_URL = os.getenv('EXTRACTOR_SERVER_URL', 'http://example.com:8001')

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'example.com')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'example_password')
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# PostgreSQL configuration
POSTGRE_HOST = os.getenv('POSTGRE_HOST', 'example.com')
POSTGRE_PORT = os.getenv('POSTGRE_PORT', '5432')
POSTGRE_USER = os.getenv('POSTGRE_USER', 'example_user')
POSTGRE_PASSWORD = os.getenv('POSTGRE_PASSWORD', 'example_password')
POSTGRE_DATABASE = os.getenv('POSTGRE_DATABASE', 'example_db')

# 新增MinIO配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "tok-label")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # "local" or "minio"

8. 扩展 ProjectBuilder 类以支持MinIO

在 toklabel/projectbuilder.py 中添加MinIO支持方法：

# 在ProjectBuilder类中添加以下方法

def import_from_minio(self, minio_prefix: str = "", bucket: str = None) -> Dict:
    """
    从MinIO导入数据到当前项目
    
    参数:
    minio_prefix (str): MinIO对象前缀，默认为空
    bucket (str, optional): 存储桶名称，默认使用配置中的桶
    
    返回:
    Dict: 导入结果
    """
    from .minio_importer import MinIOImporter
    
    importer = MinIOImporter(self.project, bucket)
    result = importer.batch_import_csv_files(prefix=minio_prefix)
    
    if not result.get("error"):
        # 更新项目的shots列表
        imported_shots = result.get("imported_shots", [])
        if hasattr(self, 'shots') and isinstance(self.shots, list):
            self.shots.extend([shot for shot in imported_shots if shot not in self.shots])
        else:
            self.shots = imported_shots
    
    return result

def export_to_minio(self, minio_prefix: str = "", bucket: str = None) -> Dict:
    """
    将当前项目数据导出到MinIO
    
    参数:
    minio_prefix (str): MinIO对象前缀
    bucket (str, optional): 存储桶名称
    
    返回:
    Dict: 导出结果
    """
    from .utils import upload_to_minio
    
    try:
        if not hasattr(self, 'processed_data') or not self.processed_data:
            return {"error": "No processed data available for export"}
        
        uploaded_files = []
        failed_files = []
        
        for shot, df in self.processed_data.items():
            file_path = f"{minio_prefix}/{self.project}/{shot}.csv" if minio_prefix else f"{self.project}/{shot}.csv"
            csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
            
            result = upload_to_minio(file_path, csv_content, bucket)
            
            if result.get("error"):
                failed_files.append({"shot": shot, "error": result["error"]})
            else:
                uploaded_files.append({"shot": shot, "path": file_path})
        
        return {
            "message": f"Exported {len(uploaded_files)} files to MinIO",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files
        }
        
    except Exception as e:
        return {"error": f"Export to MinIO error: {str(e)}"}

9. 创建环境变量配置文件

创建 .env.example 文件作为配置模板：

# Label Studio配置
LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_KEY=your_api_key_here

# 文件服务器配置
FILE_SERVER_URL=http://localhost:8000
EXTRACTOR_SERVER_URL=http://localhost:8001

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# PostgreSQL配置
POSTGRE_HOST=localhost
POSTGRE_PORT=5432
POSTGRE_USER=your_postgres_user
POSTGRE_PASSWORD=your_postgres_password
POSTGRE_DATABASE=your_database_name

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=tok-label
MINIO_SECURE=false
STORAGE_BACKEND=local

10. 更新依赖文件

创建或更新 requirements.txt 添加MinIO依赖：

# 现有依赖保持不变，添加以下MinIO相关依赖
minio>=7.1.0
fastapi>=0.68.0
uvicorn>=0.15.0
python-multipart>=0.0.5

11. 创建使用示例

创建 examples/minio_usage.py：

#!/usr/bin/env python3
"""
MinIO集成使用示例
"""

from toklabel import ProjectBuilder
from toklabel.minio_importer import MinIOImporter
from toklabel.utils import upload_to_minio, download_from_minio, list_minio_objects
import pandas as pd

def example_minio_import():
    """示例：从MinIO导入数据到Label Studio项目"""
    
    # 1. 创建项目构建器
    pb = ProjectBuilder(project="plasma_analysis")
    
    # 2. 从MinIO导入数据
    result = pb.import_from_minio(minio_prefix="plasma_data/2024")
    print("导入结果:", result)
    
    # 3. 创建Label Studio项目
    if not result.get("error"):
        pb.create_project()
        pb.create_storage()

def example_direct_minio_operations():
    """示例：直接MinIO操作"""
    
    # 1. 列出MinIO中的文件
    files = list_minio_objects(prefix="plasma_data/", recursive=True)
    print("MinIO中的文件:", files)
    
    # 2. 下载文件
    if files:
        content = download_from_minio(files[0])
        print(f"下载文件大小: {len(content)} bytes")
    
    # 3. 上传新文件
    sample_data = pd.DataFrame({
        'time': [1, 2, 3, 4, 5],
        'value': [10, 20, 30, 40, 50]
    })
    csv_content = sample_data.to_csv(index=False).encode('utf-8')
    
    upload_result = upload_to_minio("test/sample.csv", csv_content)
    print("上传结果:", upload_result)

def example_annotation_export():
    """示例：导出标注数据到MinIO"""
    
    # 使用MinIOImporter导入标注数据
    importer = MinIOImporter("plasma_analysis")
    result = importer.import_json_annotations(prefix="annotations/plasma/")
    print("标注导入结果:", result)

if __name__ == "__main__":
    print("=== MinIO导入示例 ===")
    example_minio_import()
    
    print("\n=== 直接MinIO操作示例 ===")
    example_direct_minio_operations()
    
    print("\n=== 标注数据导出示例 ===")
    example_annotation_export()

12. 创建Docker Compose配置

创建 docker-compose.minio.yml 用于本地测试：

version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: tok-label-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  file-server:
    build: ./file-server
    container_name: tok-label-file-server
    ports:
      - "8000:8000"
    environment:
      - STORAGE_BACKEND=minio
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET=tok-label
      - MINIO_SECURE=false
    depends_on:
      - minio
    volumes:
      - ./data:/data

volumes:
  minio_data:

Notes

这个第一阶段的实现提供了完整的MinIO集成支持，包括：<cite/>

1. 存储适配器模式：通过抽象接口支持本地存储和MinIO存储的无缝切换<cite/>
2. 配置驱动：基于现有的 toklabel/config.py 配置系统，添加了MinIO相关配置项 [1](#3-0) 
3. 向后兼容：保持现有API接口不变，通过环境变量控制存储后端
4. 完整的工具函数：提供了直接操作MinIO的工具函数和批量导入功能
5. ProjectBuilder集成：扩展了现有的 ProjectBuilder 类以支持MinIO数据源 [2](#3-1) 
  
实现后，用户可以通过设置 STORAGE_BACKEND=minio 环境变量来启用MinIO支持，同时保持与现有Redis和PostgreSQL集成的兼容性。 [3](#3-2) 

Wiki pages you might want to explore:
- [Overview (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1)

根据您的要求，我将提供第二阶段的完整代码实现，即在ProjectBuilder中集成MinIO数据导入功能。<cite/>

第二阶段实现：ProjectBuilder中集成MinIO数据导入功能

1. 扩展ProjectBuilder类的MinIO支持

在 toklabel/projectbuilder.py 中添加更多MinIO集成方法： [1](#4-0) 

# 在ProjectBuilder类中添加以下方法和属性

def __init__(self, project_config_file: str, **kwargs):
    # 现有初始化代码保持不变...
    defaults = {
        # 现有默认值...
        "minio_enabled": False,
        "minio_prefix": "",
        "minio_bucket": None,
        "auto_sync_minio": False,
        "minio_import_pattern": r'/(\d+)\.csv$'
    }
    
    # 从配置文件加载MinIO相关配置
    file_config = yaml.safe_load(open(project_config_file, "r", encoding="utf-8"))
    minio_config = file_config.get("minio", {})
    if minio_config:
        defaults["minio_enabled"] = minio_config.get("enabled", False)
        defaults["minio_prefix"] = minio_config.get("prefix", "")
        defaults["minio_bucket"] = minio_config.get("bucket", None)
        defaults["auto_sync_minio"] = minio_config.get("auto_sync", False)
        defaults["minio_import_pattern"] = minio_config.get("import_pattern", r'/(\d+)\.csv$')
    
    defaults.update(file_config)
    defaults.update(kwargs)
    self.__dict__.update(defaults)

def import_from_minio(self, minio_prefix: str = None, bucket: str = None, force_reload: bool = False) -> Dict:
    """
    从MinIO导入数据到当前项目
    
    参数:
    minio_prefix (str, optional): MinIO对象前缀，默认使用配置中的前缀
    bucket (str, optional): 存储桶名称，默认使用配置中的桶
    force_reload (bool): 是否强制重新加载数据
    
    返回:
    Dict: 导入结果
    """
    from .minio_importer import MinIOImporter
    from .utils import export_urls_to_redis
    
    # 使用配置中的默认值
    prefix = minio_prefix or self.minio_prefix
    bucket_name = bucket or self.minio_bucket
    
    if not self.minio_enabled:
        return {"error": "MinIO is not enabled for this project"}
    
    try:
        importer = MinIOImporter(self.project, bucket_name)
        
        # 检查是否已经导入过数据
        if not force_reload and self.data_exported:
            existing_urls = self._get_existing_urls()
            if existing_urls:
                return {
                    "message": "Data already imported from MinIO",
                    "imported_shots": list(existing_urls.keys()),
                    "use_force_reload": "Set force_reload=True to reimport"
                }
        
        # 执行批量导入
        result = importer.batch_import_csv_files(
            prefix=prefix, 
            shot_pattern=self.minio_import_pattern
        )
        
        if not result.get("error"):
            # 更新项目的shots列表
            imported_shots = result.get("imported_shots", [])
            if hasattr(self, 'shots') and isinstance(self.shots, list):
                # 合并新导入的shots，避免重复
                existing_shots = set(self.shots)
                new_shots = [shot for shot in imported_shots if shot not in existing_shots]
                self.shots.extend(new_shots)
            else:
                self.shots = imported_shots
            
            # 标记数据已导出
            self.data_exported = True
            
            # 如果启用自动同步，更新processed_data
            if self.auto_sync_minio:
                self._sync_processed_data_from_minio(imported_shots)
        
        return result
        
    except Exception as e:
        return {"error": f"MinIO import error: {str(e)}"}

def _get_existing_urls(self) -> Dict:
    """获取已存在的URL映射"""
    from .utils import list_files, parse_urls_shots
    
    try:
        file_list = list_files(self.file_path)
        if isinstance(file_list, dict) and "urls" in file_list:
            return parse_urls_shots(file_list["urls"])
        return {}
    except Exception:
        return {}

def _sync_processed_data_from_minio(self, shots: List[int]):
    """从MinIO同步处理后的数据到本地"""
    from .minio_importer import MinIOImporter
    
    try:
        importer = MinIOImporter(self.project, self.minio_bucket)
        synced_data = {}
        
        for shot in shots:
            file_path = f"{self.minio_prefix}/{self.project}/{shot}.csv"
            df = importer.download_and_convert_csv(file_path)
            if df is not None:
                synced_data[shot] = df
        
        if not hasattr(self, 'processed_data'):
            self.processed_data = {}
        self.processed_data.update(synced_data)
        
    except Exception as e:
        print(f"Warning: Failed to sync processed data from MinIO: {e}")

def export_to_minio(self, minio_prefix: str = None, bucket: str = None, include_annotations: bool = False) -> Dict:
    """
    将当前项目数据导出到MinIO
    
    参数:
    minio_prefix (str, optional): MinIO对象前缀
    bucket (str, optional): 存储桶名称
    include_annotations (bool): 是否包含标注数据
    
    返回:
    Dict: 导出结果
    """
    from .utils import upload_to_minio
    
    prefix = minio_prefix or self.minio_prefix
    bucket_name = bucket or self.minio_bucket
    
    if not self.minio_enabled:
        return {"error": "MinIO is not enabled for this project"}
    
    try:
        uploaded_files = []
        failed_files = []
        
        # 导出CSV数据
        if hasattr(self, 'processed_data') and self.processed_data:
            for shot, df in self.processed_data.items():
                file_path = f"{prefix}/{self.project}/data/{shot}.csv" if prefix else f"{self.project}/data/{shot}.csv"
                csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
                
                result = upload_to_minio(file_path, csv_content, bucket_name)
                
                if result.get("error"):
                    failed_files.append({"shot": shot, "type": "data", "error": result["error"]})
                else:
                    uploaded_files.append({"shot": shot, "type": "data", "path": file_path})
        
        # 导出标注数据（如果需要）
        if include_annotations:
            annotation_result = self._export_annotations_to_minio(prefix, bucket_name)
            uploaded_files.extend(annotation_result.get("uploaded_files", []))
            failed_files.extend(annotation_result.get("failed_files", []))
        
        return {
            "message": f"Exported {len(uploaded_files)} files to MinIO",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "bucket": bucket_name,
            "prefix": prefix
        }
        
    except Exception as e:
        return {"error": f"Export to MinIO error: {str(e)}"}

def _export_annotations_to_minio(self, prefix: str, bucket: str) -> Dict:
    """导出标注数据到MinIO"""
    from .utils import upload_to_minio
    import json
    
    uploaded_files = []
    failed_files = []
    
    try:
        # 这里假设有标注数据需要导出
        # 实际实现需要根据项目的标注数据结构调整
        if hasattr(self, 'annotations') and self.annotations:
            for shot, annotations in self.annotations.items():
                file_path = f"{prefix}/{self.project}/annotations/{shot}.json" if prefix else f"{self.project}/annotations/{shot}.json"
                json_content = json.dumps(annotations, ensure_ascii=False, indent=2).encode('utf-8')
                
                result = upload_to_minio(file_path, json_content, bucket)
                
                if result.get("error"):
                    failed_files.append({"shot": shot, "type": "annotation", "error": result["error"]})
                else:
                    uploaded_files.append({"shot": shot, "type": "annotation", "path": file_path})
    
    except Exception as e:
        failed_files.append({"error": f"Annotation export error: {str(e)}"})
    
    return {"uploaded_files": uploaded_files, "failed_files": failed_files}

def sync_with_minio(self, direction: str = "both") -> Dict:
    """
    与MinIO进行双向同步
    
    参数:
    direction (str): 同步方向 - "import", "export", "both"
    
    返回:
    Dict: 同步结果
    """
    if not self.minio_enabled:
        return {"error": "MinIO is not enabled for this project"}
    
    results = {}
    
    try:
        if direction in ["import", "both"]:
            import_result = self.import_from_minio(force_reload=True)
            results["import"] = import_result
        
        if direction in ["export", "both"]:
            export_result = self.export_to_minio(include_annotations=True)
            results["export"] = export_result
        
        return {
            "message": f"MinIO sync completed for direction: {direction}",
            "results": results
        }
        
    except Exception as e:
        return {"error": f"MinIO sync error: {str(e)}"}

def prepare_data_with_minio(self, shots=None, prefer_minio: bool = None):
    """
    准备数据，支持MinIO优先模式
    
    参数:
    shots: 炮号列表
    prefer_minio (bool): 是否优先使用MinIO数据
    
    返回:
    urls: 数据URL字典
    """
    prefer_minio = prefer_minio if prefer_minio is not None else self.minio_enabled
    
    # 如果启用MinIO且优先使用MinIO
    if prefer_minio and self.minio_enabled:
        # 首先尝试从MinIO导入数据
        minio_result = self.import_from_minio()
        if not minio_result.get("error"):
            # 如果MinIO导入成功，直接返回URL
            existing_urls = self._get_existing_urls()
            if existing_urls:
                return existing_urls
    
    # 回退到原有的数据准备流程
    return self.prepare_data(shots)

2. 创建高级MinIO数据管理器

创建新文件 toklabel/minio_data_manager.py：

import pandas as pd
from typing import List, Dict, Optional, Callable, Any
from .minio_importer import MinIOImporter
from .utils import upload_to_minio, download_from_minio, list_minio_objects
from .config import MINIO_BUCKET, REDIS_DB
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

class MinIODataManager:
    """高级MinIO数据管理器，提供数据同步、转换和管理功能"""
    
    def __init__(self, project_name: str, bucket: str = None):
        self.project_name = project_name
        self.bucket = bucket or MINIO_BUCKET
        self.importer = MinIOImporter(project_name, bucket)
        
    def batch_process_and_upload(
        self, 
        data_processor: Callable[[int], Optional[pd.DataFrame]], 
        shots: List[int],
        prefix: str = "",
        max_workers: int = 10,
        retry_failed: bool = True
    ) -> Dict:
        """
        批量处理数据并上传到MinIO
        
        参数:
        data_processor: 数据处理函数，接收shot号，返回DataFrame或None
        shots: 炮号列表
        prefix: MinIO对象前缀
        max_workers: 最大并发数
        retry_failed: 是否重试失败的任务
        
        返回:
        Dict: 处理结果
        """
        uploaded_files = []
        failed_files = []
        
        def process_single_shot(shot: int) -> Dict:
            try:
                # 处理数据
                df = data_processor(shot)
                if df is None:
                    return {"shot": shot, "status": "skipped", "reason": "No data returned"}
                
                # 上传到MinIO
                file_path = f"{prefix}/{self.project_name}/{shot}.csv" if prefix else f"{self.project_name}/{shot}.csv"
                csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
                
                result = upload_to_minio(file_path, csv_content, self.bucket)
                
                if result.get("error"):
                    return {"shot": shot, "status": "failed", "error": result["error"]}
                else:
                    return {"shot": shot, "status": "success", "path": file_path}
                    
            except Exception as e:
                return {"shot": shot, "status": "failed", "error": str(e)}
        
        # 并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_shot = {executor.submit(process_single_shot, shot): shot for shot in shots}
            
            for future in as_completed(future_to_shot):
                result = future.result()
                
                if result["status"] == "success":
                    uploaded_files.append(result)
                elif result["status"] == "failed":
                    failed_files.append(result)
                else:  # skipped
                    logger.info(f"Skipped shot {result['shot']}: {result['reason']}")
        
        # 重试失败的任务
        if retry_failed and failed_files:
            logger.info(f"Retrying {len(failed_files)} failed uploads...")
            retry_shots = [item["shot"] for item in failed_files]
            failed_files.clear()  # 

Wiki pages you might want to explore:
- [System Architecture (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1.1)
好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 toklabel/minio_data_manager.py

        # 重试失败的任务
        if retry_failed and failed_files:
            logger.info(f"Retrying {len(failed_files)} failed uploads...")
            retry_shots = [item["shot"] for item in failed_files]
            failed_files.clear()
            
            # 重试一次
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_shot = {executor.submit(process_single_shot, shot): shot for shot in retry_shots}
                
                for future in as_completed(future_to_shot):
                    result = future.result()
                    
                    if result["status"] == "success":
                        uploaded_files.append(result)
                    elif result["status"] == "failed":
                        failed_files.append(result)
        
        return {
            "message": f"Processed {len(shots)} shots, uploaded {len(uploaded_files)}, failed {len(failed_files)}",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "total_processed": len(shots)
        }
    
    def sync_annotations_from_labelstudio(self, project_id: int, prefix: str = "annotations/") -> Dict:
        """
        从Label Studio同步标注数据到MinIO
        
        参数:
        project_id: Label Studio项目ID
        prefix: MinIO存储前缀
        
        返回:
        Dict: 同步结果
        """
        try:
            from label_studio_sdk import Client
            from .config import LABEL_STUDIO_URL, LABEL_STUDIO_API_KEY
            
            # 连接Label Studio
            ls = Client(url=LABEL_STUDIO_URL, api_key=LABEL_STUDIO_API_KEY)
            project = ls.get_project(project_id)
            
            # 获取所有标注任务
            tasks = project.get_tasks()
            
            uploaded_annotations = []
            failed_annotations = []
            
            for task in tasks:
                try:
                    # 提取shot号
                    shot = task.get('data', {}).get('shot')
                    if not shot:
                        continue
                    
                    # 获取标注数据
                    annotations = task.get('annotations', [])
                    if not annotations:
                        continue
                    
                    # 上传到MinIO
                    file_path = f"{prefix}/{self.project_name}/{shot}.json"
                    json_content = json.dumps(annotations, ensure_ascii=False, indent=2).encode('utf-8')
                    
                    result = upload_to_minio(file_path, json_content, self.bucket)
                    
                    if result.get("error"):
                        failed_annotations.append({"shot": shot, "error": result["error"]})
                    else:
                        uploaded_annotations.append({"shot": shot, "path": file_path})
                        
                except Exception as e:
                    logger.error(f"Error processing task {task.get('id')}: {e}")
                    failed_annotations.append({"task_id": task.get('id'), "error": str(e)})
            
            return {
                "message": f"Synced {len(uploaded_annotations)} annotations from Label Studio",
                "uploaded_annotations": uploaded_annotations,
                "failed_annotations": failed_annotations
            }
            
        except Exception as e:
            return {"error": f"Label Studio sync error: {str(e)}"}
    
    def create_data_pipeline(self, pipeline_config: Dict) -> Dict:
        """
        创建数据处理管道
        
        参数:
        pipeline_config: 管道配置
        {
            "source": {"type": "postgres", "config": {...}},
            "processors": [{"type": "filter", "config": {...}}, ...],
            "destination": {"type": "minio", "prefix": "..."}
        }
        
        返回:
        Dict: 管道执行结果
        """
        try:
            source_config = pipeline_config.get("source", {})
            processors = pipeline_config.get("processors", [])
            destination = pipeline_config.get("destination", {})
            
            # 数据源处理
            if source_config.get("type") == "postgres":
                data_loader = self._create_postgres_loader(source_config.get("config", {}))
            elif source_config.get("type") == "minio":
                data_loader = self._create_minio_loader(source_config.get("config", {}))
            else:
                return {"error": f"Unsupported source type: {source_config.get('type')}"}
            
            # 数据处理器链
            processor_chain = []
            for proc_config in processors:
                processor = self._create_processor(proc_config)
                if processor:
                    processor_chain.append(processor)
            
            # 执行管道
            def pipeline_processor(shot: int) -> Optional[pd.DataFrame]:
                try:
                    # 加载数据
                    df = data_loader(shot)
                    if df is None:
                        return None
                    
                    # 应用处理器链
                    for processor in processor_chain:
                        df = processor(df)
                        if df is None:
                            return None
                    
                    return df
                    
                except Exception as e:
                    logger.error(f"Pipeline error for shot {shot}: {e}")
                    return None
            
            # 获取要处理的shots
            shots = source_config.get("config", {}).get("shots", [])
            if not shots:
                return {"error": "No shots specified in source config"}
            
            # 执行批量处理
            result = self.batch_process_and_upload(
                data_processor=pipeline_processor,
                shots=shots,
                prefix=destination.get("prefix", ""),
                max_workers=pipeline_config.get("max_workers", 10)
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Pipeline creation error: {str(e)}"}
    
    def _create_postgres_loader(self, config: Dict) -> Callable[[int], Optional[pd.DataFrame]]:
        """创建PostgreSQL数据加载器"""
        def postgres_loader(shot: int) -> Optional[pd.DataFrame]:
            try:
                from .utils import export_postgres_data
                
                name_table_columns = config.get("name_table_columns", {})
                t_min = config.get("t_min", -float('inf'))
                t_max = config.get("t_max", float('inf'))
                resolution = config.get("resolution", 1e-3)
                
                data = export_postgres_data(
                    [shot], name_table_columns, t_min, t_max, resolution
                )
                
                return data.get(shot)
                
            except Exception as e:
                logger.error(f"PostgreSQL loader error for shot {shot}: {e}")
                return None
        
        return postgres_loader
    
    def _create_minio_loader(self, config: Dict) -> Callable[[int], Optional[pd.DataFrame]]:
        """创建MinIO数据加载器"""
        def minio_loader(shot: int) -> Optional[pd.DataFrame]:
            try:
                prefix = config.get("prefix", "")
                file_path = f"{prefix}/{shot}.csv"
                
                return self.importer.download_and_convert_csv(file_path)
                
            except Exception as e:
                logger.error(f"MinIO loader error for shot {shot}: {e}")
                return None
        
        return minio_loader
    
    def _create_processor(self, proc_config: Dict) -> Optional[Callable[[pd.DataFrame], Optional[pd.DataFrame]]]:
        """创建数据处理器"""
        proc_type = proc_config.get("type")
        config = proc_config.get("config", {})
        
        if proc_type == "filter":
            def filter_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    condition = config.get("condition")
                    if condition:
                        # 简单的条件过滤，可以扩展为更复杂的表达式
                        return df.query(condition)
                    return df
                except Exception as e:
                    logger.error(f"Filter processor error: {e}")
                    return None
            return filter_processor
        
        elif proc_type == "resample":
            def resample_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    time_column = config.get("time_column", "time")
                    frequency = config.get("frequency", "1ms")
                    
                    df_resampled = df.set_index(time_column).resample(frequency).mean()
                    return df_resampled.reset_index()
                except Exception as e:
                    logger.error(f"Resample processor error: {e}")
                    return None
            return resample_processor
        
        elif proc_type == "normalize":
            def normalize_processor(df: pd.DataFrame) -> Optional[pd.DataFrame]:
                try:
                    columns = config.get("columns", [])
                    method = config.get("method", "minmax")
                    
                    df_normalized = df.copy()
                    for col in columns:
                        if col in df.columns:
                            if method == "minmax":
                                min_val = df[col].min()
                                max_val = df[col].max()
                                df_normalized[col] = (df[col] - min_val) / (max_val - min_val)
                            elif method == "zscore":
                                mean_val = df[col].mean()
                                std_val = df[col].std()
                                df_normalized[col] = (df[col] - mean_val) / std_val
                    
                    return df_normalized
                except Exception as e:
                    logger.error(f"Normalize processor error: {e}")
                    return None
            return normalize_processor
        
        else:
            logger.warning(f"Unknown processor type: {proc_type}")
            return None

3. 创建MinIO配置管理器

创建新文件 toklabel/minio_config_manager.py：

import yaml
import os
from typing import Dict, List, Optional
from .config import MINIO_BUCKET, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
import logging

logger = logging.getLogger(__name__)

class MinIOConfigManager:
    """MinIO配置管理器，处理项目配置和MinIO集成设置"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config = {}
        if config_file and os.path.exists(config_file):
            self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config file {self.config_file}: {e}")
            self.config = {}
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Error saving config file {self.config_file}: {e}")
    
    def enable_minio(self, 
                     bucket: str = None, 
                     prefix: str = "", 
                     auto_sync: bool = False,
                     import_pattern: str = r'/(\d+)\.csv$') -> Dict:
        """
        启用MinIO集成
        
        参数:
        bucket: 存储桶名称
        prefix: 对象前缀
        auto_sync: 是否自动同步
        import_pattern: 导入文件名模式
        
        返回:
        Dict: 操作结果
        """
        try:
            minio_config = {
                "enabled": True,
                "bucket": bucket or MINIO_BUCKET,
                "prefix": prefix,
                "auto_sync": auto_sync,
                "import_pattern": import_pattern,
                "endpoint": MINIO_ENDPOINT,
                "connection": {
                    "access_key": MINIO_ACCESS_KEY,
                    "secret_key": MINIO_SECRET_KEY
                }
            }
            
            self.config["minio"] = minio_config
            
            if self.config_file:
                self.save_config()
            
            return {
                "message": "MinIO integration enabled successfully",
                "config": minio_config
            }
            
        except Exception as e:
            return {"error": f"Failed to enable MinIO: {str(e)}"}
    
    def disable_minio(self) -> Dict:
        """禁用MinIO集成"""
        try:
            if "minio" in self.config:
                self.config["minio"]["enabled"] = False
                
                if self.config_file:
                    self.save_config()
                
                return {"message": "MinIO integration disabled successfully"}
            else:
                return {"message": "MinIO was not enabled"}
                
        except Exception as e:
            return {"error": f"Failed to disable MinIO: {str(e)}"}
    
    def get_minio_config(self) -> Dict:
        """获取MinIO配置"""
        return self.config.get("minio", {})
    
    def is_minio_enabled(self) -> bool:
        """检查MinIO是否启用"""
        minio_config = self.get_minio_config()
        return minio_config.get("enabled", False)
    
    def create_data_pipeline_config(self, 
                                   source_type: str,
                                   source_config: Dict,
                                   processors: List[Dict] = None,
                                   destination_prefix: str = "") -> Dict:
        """
        创建数据管道配置
        
        参数:
        source_type: 数据源类型 ("postgres", "minio")
        source_config: 数据源配置
        processors: 处理器列表
        destination_prefix: 目标前缀
        
        返回:
        Dict: 管道配置
        """
        pipeline_config = {
            "source": {
                "type": source_type,
                "config": source_config
            },
            "processors": processors or [],
            "destination": {
                "type": "minio",
                "prefix": destination_prefix
            },
            "max_workers": 10
        }
        
        # 保存到配置文件
        if "pipelines" not in self.config:
            self.config["pipelines"] = []
        
        self.config["pipelines"].append(pipeline_config)
        
        if self.config_file:
            self.save_config()
        
        return pipeline_config
    
    def get_pipeline_configs(self) -> List[Dict]:
        """获取所有管道配置

Wiki pages you might want to explore:
- [Overview (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1)


好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 toklabel/minio_config_manager.py

    def get_pipeline_configs(self) -> List[Dict]:
        """获取所有管道配置"""
        return self.config.get("pipelines", [])
    
    def remove_pipeline_config(self, index: int) -> Dict:
        """删除指定索引的管道配置"""
        try:
            pipelines = self.config.get("pipelines", [])
            if 0 <= index < len(pipelines):
                removed_pipeline = pipelines.pop(index)
                if self.config_file:
                    self.save_config()
                return {
                    "message": f"Pipeline config at index {index} removed successfully",
                    "removed_config": removed_pipeline
                }
            else:
                return {"error": f"Invalid pipeline index: {index}"}
        except Exception as e:
            return {"error": f"Failed to remove pipeline config: {str(e)}"}
    
    def update_minio_settings(self, **kwargs) -> Dict:
        """更新MinIO设置"""
        try:
            if "minio" not in self.config:
                self.config["minio"] = {}
            
            # 更新设置
            for key, value in kwargs.items():
                if key in ["bucket", "prefix", "auto_sync", "import_pattern", "enabled"]:
                    self.config["minio"][key] = value
            
            if self.config_file:
                self.save_config()
            
            return {
                "message": "MinIO settings updated successfully",
                "updated_config": self.config["minio"]
            }
        except Exception as e:
            return {"error": f"Failed to update MinIO settings: {str(e)}"}

4. 创建项目配置模板扩展

创建新文件 project-config-minio.yaml 作为MinIO集成的配置模板：

# 项目基本配置
project: "plasma_analysis_minio"
file_path: "plasma_data"
shots: [240830026, 240830027, 240830028, 240830029]

# 数据源配置
name_table_columns:
  ammeter:
    - "ammeter"
    - ["CS1", "CS2", "PFP1"]
  flux_loop:
    - "flux_loop" 
    - [1, 2, 3, 8, 10]

# 时间范围和分辨率
t_min: 0.1
t_max: 1.0
resolution: 1e-3

# 标签配置
label_table:
  - ["ip_time", ["effective"]]
  - ["disruption", ["stable", "unstable", "disruptive"]]

# MinIO集成配置
minio:
  enabled: true
  bucket: "tok-label"
  prefix: "plasma_data/2024"
  auto_sync: true
  import_pattern: '/(\d+)\.csv$'
  connection:
    endpoint: "localhost:9000"
    access_key: "minioadmin"
    secret_key: "minioadmin"
    secure: false

# 数据处理管道配置
pipelines:
  - source:
      type: "postgres"
      config:
        shots: [240830026, 240830027, 240830028, 240830029]
        name_table_columns:
          ammeter: ["ammeter", ["CS1", "CS2", "PFP1"]]
          flux_loop: ["flux_loop", [1, 2, 3, 8, 10]]
        t_min: 0.1
        t_max: 1.0
        resolution: 1e-3
    processors:
      - type: "filter"
        config:
          condition: "time >= 0.1 and time <= 1.0"
      - type: "resample"
        config:
          time_column: "time"
          frequency: "1ms"
      - type: "normalize"
        config:
          columns: ["CS1", "CS2", "PFP1"]
          method: "minmax"
    destination:
      type: "minio"
      prefix: "processed_data/plasma"
    max_workers: 10

# Label Studio项目配置
label_studio:
  title: "Plasma Analysis with MinIO"
  description: "Time series data annotation project with MinIO backend"
  label_config: |
    <View>
      <Header value="Plasma Data Analysis"/>
      <TimeSeries name="ts" value="$csv" valueType="url">
        <Channel column="time"/>
        <Channel column="CS1" strokeColor="#1f77b4"/>
        <Channel column="CS2" strokeColor="#ff7f0e"/>
        <Channel column="PFP1" strokeColor="#2ca02c"/>
      </TimeSeries>
      <TimeSeriesLabels name="label" toName="ts">
        <Label value="effective" background="green"/>
        <Label value="stable" background="blue"/>
        <Label value="unstable" background="yellow"/>
        <Label value="disruptive" background="red"/>
      </TimeSeriesLabels>
    </View>

5. 创建MinIO集成的工作流管理器

创建新文件 toklabel/minio_workflow_manager.py：

import logging
from typing import Dict, List, Optional
from .projectbuilder import ProjectBuilder
from .minio_data_manager import MinIODataManager
from .minio_config_manager import MinIOConfigManager
from .utils import export_annotation, simple_json_convertor
from .annotation_manager import AnnotationManager

logger = logging.getLogger(__name__)

class MinIOWorkflowManager:
    """MinIO集成工作流管理器，提供完整的数据处理和标注工作流"""
    
    def __init__(self, config_file: str):
        self.config_manager = MinIOConfigManager(config_file)
        self.project_builder = None
        self.data_manager = None
        
    def initialize_project(self, **kwargs) -> Dict:
        """初始化项目"""
        try:
            # 创建ProjectBuilder实例
            self.project_builder = ProjectBuilder(self.config_manager.config_file, **kwargs)
            
            # 创建数据管理器
            self.data_manager = MinIODataManager(
                self.project_builder.project,
                self.project_builder.minio_bucket
            )
            
            return {
                "message": "Project initialized successfully",
                "project_name": self.project_builder.project,
                "minio_enabled": self.project_builder.minio_enabled
            }
        except Exception as e:
            return {"error": f"Failed to initialize project: {str(e)}"}
    
    def run_complete_workflow(self, ls_client, create_new_project: bool = True) -> Dict:
        """运行完整的工作流：数据准备 -> 项目创建 -> 存储同步"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized. Call initialize_project() first."}
            
            results = {}
            
            # 1. 数据准备
            if self.project_builder.minio_enabled:
                # 使用MinIO数据源
                data_result = self.project_builder.import_from_minio()
                results["data_import"] = data_result
                
                if data_result.get("error"):
                    return {"error": f"Data import failed: {data_result['error']}"}
            else:
                # 使用传统数据准备流程
                urls = self.project_builder.prepare_data()
                results["data_preparation"] = {"urls": urls}
            
            # 2. 创建Label Studio项目
            if create_new_project:
                project = self.project_builder.create_project(ls_client)
                results["project_creation"] = {"project_id": project.id}
            
            # 3. 创建存储同步
            storage = self.project_builder.create_storage(ls_client)
            results["storage_creation"] = {"storage_id": storage.id}
            
            return {
                "message": "Complete workflow executed successfully",
                "results": results
            }
            
        except Exception as e:
            return {"error": f"Workflow execution failed: {str(e)}"}
    
    def run_data_pipeline(self, pipeline_index: int = 0) -> Dict:
        """运行指定的数据处理管道"""
        try:
            if not self.data_manager:
                return {"error": "Data manager not initialized"}
            
            pipelines = self.config_manager.get_pipeline_configs()
            if not pipelines or pipeline_index >= len(pipelines):
                return {"error": f"Invalid pipeline index: {pipeline_index}"}
            
            pipeline_config = pipelines[pipeline_index]
            result = self.data_manager.create_data_pipeline(pipeline_config)
            
            return result
            
        except Exception as e:
            return {"error": f"Pipeline execution failed: {str(e)}"}
    
    def export_and_store_annotations(self, ls_client, project_id: int, table_name: str = None) -> Dict:
        """导出标注数据并存储到PostgreSQL和MinIO"""
        try:
            # 1. 从Label Studio导出标注
            export_json = export_annotation(
                ls_client, 
                project_id, 
                json_min=True, 
                exclude_skipped=False, 
                only_with_annotation=True
            )
            
            # 2. 转换标注数据
            label_list = simple_json_convertor(
                export_json, 
                True, 
                label_group_name='annotations'
            )
            
            # 3. 存储到PostgreSQL
            table_name = table_name or self.project_builder.project
            label_manager = AnnotationManager()
            
            # 创建标注表（如果不存在）
            label_manager.create_annotation_table(
                table_name, 
                label_name='annotations',
                unique_shot=True, 
                point_allowed=False
            )
            
            # 插入标注数据
            pg_result = label_manager.insert_annotations(
                table_name, 
                label_list, 
                on_conflict='shot'
            )
            
            # 4. 同步标注到MinIO
            minio_result = None
            if self.project_builder.minio_enabled:
                minio_result = self.data_manager.sync_annotations_from_labelstudio(
                    project_id, 
                    prefix="annotations/"
                )
            
            return {
                "message": "Annotations exported and stored successfully",
                "postgresql_result": pg_result,
                "minio_result": minio_result,
                "annotation_count": len(label_list)
            }
            
        except Exception as e:
            return {"error": f"Annotation export failed: {str(e)}"}
    
    def sync_data_bidirectional(self, direction: str = "both") -> Dict:
        """双向数据同步"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized"}
            
            if not self.project_builder.minio_enabled:
                return {"error": "MinIO is not enabled for this project"}
            
            result = self.project_builder.sync_with_minio(direction)
            return result
            
        except Exception as e:
            return {"error": f"Bidirectional sync failed: {str(e)}"}
    
    def cleanup_local_storage(self, ls_client, storage_id: int, keep_storage_link: bool = False) -> Dict:
        """清理本地存储"""
        try:
            from .utils import delete_storage
            
            result = delete_storage(ls_client, storage_id, keep_storage_link)
            return result
            
        except Exception as e:
            return {"error": f"Storage cleanup failed: {str(e)}"}
    
    def get_project_status(self) -> Dict:
        """获取项目状态"""
        try:
            if not self.project_builder:
                return {"error": "Project not initialized"}
            
            status = {
                "project_name": self.project_builder.project,
                "minio_enabled": self.project_builder.minio_enabled,
                "data_exported": getattr(self.project_builder, 'data_exported', False),
                "shots_count": len(getattr(self.project_builder, 'shots', [])),
                "minio_config": self.config_manager.get_minio_config(),
                "pipeline_count": len(self.config_manager.get_pipeline_configs())
            }
            
            return {"status": status}
            
        except Exception as e:
            return {"error": f"Failed to get project status: {str(e)}"}

6. 创建完整的使用示例

创建 examples/complete_minio_workflow.py：

#!/usr/bin/env python3
"""
完整的MinIO集成工作流示例
"""

import toklabel
from toklabel.minio_workflow_manager import MinIOWorkflowManager
import json

def main():
    """主工作流示例"""
    
    # 1. 连接Label Studio
    API_KEY = 'your_api_key_here'
    ls = toklabel.connect_Label_Studio(API_key=API_KEY)
    
    # 2. 初始化工作流管理器
    workflow = MinIOWorkflowManager('project-config-minio.yaml')
    
    # 3. 初始化项目
    init_result = workflow.initialize_project()
    print("项目初始化结果:", json.dumps(init_result, indent=2, ensure_ascii=False))
    
    if init_result.get("error"):
        return
    
    # 4. 运行完整工作流
    workflow_result = workflow.run_complete_workflow(ls, create_new_project=True)
    print("工作流执行结果:", json.dumps(workflow_result, indent=2, ensure_ascii=False))
    
    if workflow_result.get("error"):
        return
    
    project_id = workflow_result["results"]["project_creation"]["project_id"]
    storage_id = workflow_result["results"]["storage_creation"]["storage_id"]
    
    # 5. 运行数据处理管道
    pipeline_result = workflow.run_data_pipeline(pipeline_index=0)
    print("数据管道执行结果:", json.dumps(pipeline_result, indent=2, ensure_ascii=False))
    
    # 6. 获取项目状态
    status = workflow.get_project_status()
    print("项目状态:", json.dumps(status, indent=2, ensure_ascii=False))
    
    # 7. 模拟标注完成后的导出流程
    print("\n=== 标注完成后的操作 ===")
    
    # 导出并存储标注
    annotation_result = workflow.export_and_store_annotations(
        ls, project_id, table_name="plasma_annotations"
    )
    print("标注导出结果:", json.dumps(annotation_result, indent=2, ensure_ascii=False))
    
    # 8. 双向同步

Wiki pages you might want to explore:
- [System Architecture (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1.1)

好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 examples/complete_minio_workflow.py

    # 8. 双向同步
    sync_result = workflow.sync_data_bidirectional(direction="both")
    print("双向同步结果:", json.dumps(sync_result, indent=2, ensure_ascii=False))
    
    # 9. 清理本地存储（可选）
    cleanup_result = workflow.cleanup_local_storage(ls, storage_id, keep_storage_link=True)
    print("存储清理结果:", json.dumps(cleanup_result, indent=2, ensure_ascii=False))

def advanced_pipeline_example():
    """高级管道使用示例"""
    
    # 1. 创建配置管理器
    from toklabel.minio_config_manager import MinIOConfigManager
    config_manager = MinIOConfigManager('project-config-minio.yaml')
    
    # 2. 动态创建新的数据管道
    pipeline_config = config_manager.create_data_pipeline_config(
        source_type="postgres",
        source_config={
            "shots": [240830030, 240830031],
            "name_table_columns": {
                "ammeter": ["ammeter", ["CS1", "CS2"]],
                "flux_loop": ["flux_loop", [1, 2, 3]]
            },
            "t_min": 0.0,
            "t_max": 2.0,
            "resolution": 1e-3
        },
        processors=[
            {
                "type": "filter",
                "config": {"condition": "time >= 0.1 and time <= 1.5"}
            },
            {
                "type": "normalize",
                "config": {"columns": ["CS1", "CS2"], "method": "zscore"}
            }
        ],
        destination_prefix="advanced_processed"
    )
    
    print("创建的管道配置:", json.dumps(pipeline_config, indent=2, ensure_ascii=False))
    
    # 3. 执行管道
    from toklabel.minio_data_manager import MinIODataManager
    data_manager = MinIODataManager("plasma_analysis_advanced")
    pipeline_result = data_manager.create_data_pipeline(pipeline_config)
    print("管道执行结果:", json.dumps(pipeline_result, indent=2, ensure_ascii=False))

def batch_annotation_sync_example():
    """批量标注同步示例"""
    
    from toklabel.minio_data_manager import MinIODataManager
    
    # 创建数据管理器
    data_manager = MinIODataManager("plasma_analysis")
    
    # 假设有一个Label Studio项目ID
    project_id = 123
    
    # 同步标注数据到MinIO
    sync_result = data_manager.sync_annotations_from_labelstudio(
        project_id, 
        prefix="annotations/plasma_2024/"
    )
    print("标注同步结果:", json.dumps(sync_result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    print("=== 完整工作流示例 ===")
    main()
    
    print("\n=== 高级管道示例 ===")
    advanced_pipeline_example()
    
    print("\n=== 批量标注同步示例 ===")
    batch_annotation_sync_example()

7. 创建MinIO监控和健康检查工具

创建新文件 toklabel/minio_monitor.py：

import time
import logging
from typing import Dict, List, Optional
from .utils import list_minio_objects, download_from_minio
from .config import MINIO_BUCKET, MINIO_ENDPOINT
from minio import Minio
from minio.error import S3Error
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MinIOMonitor:
    """MinIO监控器，提供健康检查和数据监控功能"""
    
    def __init__(self, bucket: str = None):
        self.bucket = bucket or MINIO_BUCKET
        self.client = None
        self._initialize_client()
        
    def _initialize_client(self):
        """初始化MinIO客户端"""
        try:
            from .config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE
            self.client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE
            )
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
    
    def health_check(self) -> Dict:
        """MinIO健康检查"""
        try:
            if not self.client:
                return {"status": "error", "message": "MinIO client not initialized"}
            
            # 检查连接
            buckets = self.client.list_buckets()
            
            # 检查目标桶是否存在
            bucket_exists = self.client.bucket_exists(self.bucket)
            
            # 获取桶信息
            bucket_info = None
            if bucket_exists:
                objects = list(self.client.list_objects(self.bucket, recursive=False))
                bucket_info = {
                    "object_count": len(objects),
                    "bucket_name": self.bucket
                }
            
            return {
                "status": "healthy",
                "endpoint": MINIO_ENDPOINT,
                "bucket_exists": bucket_exists,
                "bucket_info": bucket_info,
                "total_buckets": len(buckets),
                "timestamp": datetime.now().isoformat()
            }
            
        except S3Error as e:
            return {
                "status": "error",
                "message": f"MinIO S3 error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"MinIO connection error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_storage_statistics(self, prefix: str = "") -> Dict:
        """获取存储统计信息"""
        try:
            if not self.client:
                return {"error": "MinIO client not initialized"}
            
            objects = list(self.client.list_objects(self.bucket, prefix=prefix, recursive=True))
            
            # 统计信息
            total_objects = len(objects)
            total_size = sum(obj.size for obj in objects if obj.size)
            
            # 按文件类型分组
            file_types = {}
            for obj in objects:
                ext = obj.object_name.split('.')[-1].lower() if '.' in obj.object_name else 'no_ext'
                if ext not in file_types:
                    file_types[ext] = {"count": 0, "size": 0}
                file_types[ext]["count"] += 1
                file_types[ext]["size"] += obj.size if obj.size else 0
            
            # 最近修改的文件
            recent_objects = sorted(objects, key=lambda x: x.last_modified, reverse=True)[:10]
            recent_files = [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat()
                }
                for obj in recent_objects
            ]
            
            return {
                "total_objects": total_objects,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": file_types,
                "recent_files": recent_files,
                "bucket": self.bucket,
                "prefix": prefix
            }
            
        except Exception as e:
            return {"error": f"Failed to get storage statistics: {str(e)}"}
    
    def monitor_data_changes(self, prefix: str = "", check_interval: int = 60) -> None:
        """监控数据变化（后台运行）"""
        def monitor_loop():
            last_object_list = set()
            
            while True:
                try:
                    current_objects = set(list_minio_objects(prefix=prefix, bucket=self.bucket, recursive=True))
                    
                    # 检查新增文件
                    new_objects = current_objects - last_object_list
                    if new_objects:
                        logger.info(f"New objects detected: {list(new_objects)}")
                    
                    # 检查删除文件
                    deleted_objects = last_object_list - current_objects
                    if deleted_objects:
                        logger.info(f"Deleted objects detected: {list(deleted_objects)}")
                    
                    last_object_list = current_objects
                    time.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                    time.sleep(check_interval)
        
        # 在后台线程中运行监控
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info(f"Started MinIO monitor for prefix '{prefix}' with {check_interval}s interval")

8. 创建MinIO数据验证器

创建新文件 toklabel/minio_validator.py：

import pandas as pd
from typing import Dict, List, Optional, Tuple
from .minio_importer import MinIOImporter
from .utils import download_from_minio
import logging
import json

logger = logging.getLogger(__name__)

class MinIODataValidator:
    """MinIO数据验证器，验证数据完整性和格式正确性"""
    
    def __init__(self, project_name: str, bucket: str = None):
        self.project_name = project_name
        self.importer = MinIOImporter(project_name, bucket)
        
    def validate_csv_files(self, prefix: str = "", required_columns: List[str] = None) -> Dict:
        """
        验证CSV文件格式和内容
        
        参数:
        prefix: MinIO对象前缀
        required_columns: 必需的列名列表
        
        返回:
        Dict: 验证结果
        """
        try:
            files = self.importer.list_available_files(prefix)
            csv_files = [f for f in files if f.endswith('.csv')]
            
            if not csv_files:
                return {"error": "No CSV files found for validation"}
            
            validation_results = []
            valid_files = []
            invalid_files = []
            
            for file_path in csv_files:
                file_result = {
                    "file": file_path,
                    "valid": True,
                    "issues": []
                }
                
                try:
                    # 下载并解析CSV
                    df = self.importer.download_and_convert_csv(file_path)
                    if df is None:
                        file_result["valid"] = False
                        file_result["issues"].append("Failed to parse CSV")
                        invalid_files.append(file_path)
                        validation_results.append(file_result)
                        continue
                    
                    # 检查必需列
                    if required_columns:
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        if missing_columns:
                            file_result["valid"] = False
                            file_result["issues"].append(f"Missing columns: {missing_columns}")
                    
                    # 检查数据完整性
                    if df.empty:
                        file_result["valid"] = False
                        file_result["issues"].append("Empty DataFrame")
                    
                    # 检查数据类型
                    if 'time' in df.columns:
                        if not pd.api.types.is_numeric_dtype(df['time']):
                            file_result["issues"].append("Time column is not numeric")
                    
                    # 检查重复值
                    if df.duplicated().any():
                        file_result["issues"].append("Contains duplicate rows")
                    
                    # 检查缺失值
                    missing_data = df.isnull().sum()
                    if missing_data.any():
                        file_result["issues"].append(f"Missing values: {missing_data.to_dict()}")
                    
                    file_result["row_count"] = len(df)
                    file_result["column_count"] = len(df.columns)
                    file_result["columns"] = list(df.columns)
                    
                    if file_result["valid"]:
                        valid_files.append(file_path)
                    else:
                        invalid_files.append(file_path)
                    
                except Exception as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"Validation error: {str(e)}")
                    invalid_files.append(file_path)
                
                validation_results.append(file_result)
            
            return {
                "message": f"Validated {len(csv_files)} CSV files",
                "total_files": len(csv_files),
                "valid_files": len(valid_files),
                "invalid_files": len(invalid_files),
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {"error": f"Validation error: {str(e)}"}
    
    def validate_data_consistency(self, shots: List[int], prefix: str = "") -> Dict:
        """
        验证多个shot数据的一致性
        
        参数:
        shots: 炮号列表
        prefix: MinIO对象前缀
        
        返回:
        Dict: 一致性验证结果
        """
        try:
            consistency_issues = []
            shot_data = {}
            
            # 加载所有shot数据
            for shot in shots:
                file_path = f"{prefix}/{self.project_name}/{shot}.csv" if prefix else f"{self.project_name}/{shot}.csv"
                df = self.importer.download_and_convert_csv(file_path)
                if df is not None:
                    shot_data[shot] = df
                else:
                    consistency_issues.append(f"Failed to load data for shot {shot}")
            
            if not shot_data:
                return {"error": "No valid shot data found"}
            
            # 检查列一致性
            all_columns = [set(df.columns) for df in shot_data.values()]
            if len(set(frozenset(cols) for cols in all_columns)) > 1:
                consistency_issues.append("Inconsistent column names across shots")
            
            # 检查时间范围一致性
            time_ranges = {}
            for shot, df in shot_data.items():
                if 'time' in df.columns:
                    time_ranges[shot] = {
                        "min": df['time'].min(),
                        "max": df['time'].max(),
                        "count": len(df)
                    

Wiki pages you might want to explore:
- [Overview (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1)

好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 toklabel/minio_validator.py

            # 检查时间范围一致性
            time_ranges = {}
            for shot, df in shot_data.items():
                if 'time' in df.columns:
                    time_ranges[shot] = {
                        "min": df['time'].min(),
                        "max": df['time'].max(),
                        "count": len(df)
                    }
            
            # 检查时间范围差异
            if time_ranges:
                min_times = [tr["min"] for tr in time_ranges.values()]
                max_times = [tr["max"] for tr in time_ranges.values()]
                counts = [tr["count"] for tr in time_ranges.values()]
                
                if max(min_times) - min(min_times) > 0.1:  # 100ms差异
                    consistency_issues.append("Significant time range start differences")
                
                if max(max_times) - min(max_times) > 0.1:  # 100ms差异
                    consistency_issues.append("Significant time range end differences")
                
                if max(counts) - min(counts) > len(shot_data) * 0.1:  # 10%差异
                    consistency_issues.append("Significant data point count differences")
            
            return {
                "message": f"Validated consistency for {len(shot_data)} shots",
                "shots_validated": list(shot_data.keys()),
                "consistency_issues": consistency_issues,
                "time_ranges": time_ranges,
                "is_consistent": len(consistency_issues) == 0
            }
            
        except Exception as e:
            return {"error": f"Consistency validation error: {str(e)}"}
    
    def validate_annotation_files(self, prefix: str = "annotations/") -> Dict:
        """
        验证标注文件的格式和内容
        
        参数:
        prefix: 标注文件的MinIO前缀
        
        返回:
        Dict: 验证结果
        """
        try:
            files = self.importer.list_available_files(prefix)
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                return {"error": "No JSON annotation files found"}
            
            validation_results = []
            valid_annotations = []
            invalid_annotations = []
            
            for file_path in json_files:
                file_result = {
                    "file": file_path,
                    "valid": True,
                    "issues": [],
                    "annotation_count": 0
                }
                
                try:
                    content = download_from_minio(file_path, self.importer.bucket)
                    annotation_data = json.loads(content.decode('utf-8'))
                    
                    # 检查JSON结构
                    if not isinstance(annotation_data, (list, dict)):
                        file_result["valid"] = False
                        file_result["issues"].append("Invalid JSON structure")
                    
                    # 如果是列表，检查每个标注
                    if isinstance(annotation_data, list):
                        file_result["annotation_count"] = len(annotation_data)
                        
                        for i, annotation in enumerate(annotation_data):
                            if not isinstance(annotation, dict):
                                file_result["issues"].append(f"Annotation {i} is not a dictionary")
                                continue
                            
                            # 检查必需字段
                            required_fields = ['id', 'result']
                            missing_fields = [field for field in required_fields if field not in annotation]
                            if missing_fields:
                                file_result["issues"].append(f"Annotation {i} missing fields: {missing_fields}")
                    
                    elif isinstance(annotation_data, dict):
                        file_result["annotation_count"] = 1
                        
                        # 检查单个标注的结构
                        if 'annotations' in annotation_data:
                            file_result["annotation_count"] = len(annotation_data['annotations'])
                    
                    if file_result["issues"]:
                        file_result["valid"] = False
                        invalid_annotations.append(file_path)
                    else:
                        valid_annotations.append(file_path)
                    
                except json.JSONDecodeError as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"JSON decode error: {str(e)}")
                    invalid_annotations.append(file_path)
                except Exception as e:
                    file_result["valid"] = False
                    file_result["issues"].append(f"Validation error: {str(e)}")
                    invalid_annotations.append(file_path)
                
                validation_results.append(file_result)
            
            return {
                "message": f"Validated {len(json_files)} annotation files",
                "total_files": len(json_files),
                "valid_files": len(valid_annotations),
                "invalid_files": len(invalid_annotations),
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {"error": f"Annotation validation error: {str(e)}"}

9. 创建MinIO集成测试工具

创建新文件 tests/test_minio_integration.py：

import unittest
import tempfile
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from toklabel.minio_importer import MinIOImporter
from toklabel.minio_data_manager import MinIODataManager
from toklabel.minio_config_manager import MinIOConfigManager
from toklabel.minio_validator import MinIODataValidator

class TestMinIOIntegration(unittest.TestCase):
    """MinIO集成测试"""
    
    def setUp(self):
        """测试设置"""
        self.project_name = "test_project"
        self.bucket_name = "test-bucket"
        
        # 创建临时配置文件
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_content = """
project: test_project
minio:
  enabled: true
  bucket: test-bucket
  prefix: test_data
  auto_sync: false
"""
        self.temp_config.write(config_content)
        self.temp_config.close()
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.temp_config.name)
    
    @patch('toklabel.minio_importer.download_from_minio')
    @patch('toklabel.minio_importer.list_minio_objects')
    def test_minio_importer_batch_import(self, mock_list_objects, mock_download):
        """测试MinIO批量导入功能"""
        # 模拟MinIO对象列表
        mock_list_objects.return_value = [
            "test_data/test_project/240830026.csv",
            "test_data/test_project/240830027.csv"
        ]
        
        # 模拟CSV内容
        test_csv = "time,value\n1.0,10.0\n2.0,20.0\n"
        mock_download.return_value = test_csv.encode('utf-8')
        
        # 创建导入器并测试
        importer = MinIOImporter(self.project_name, self.bucket_name)
        
        with patch('toklabel.minio_importer.upload_dataframe') as mock_upload:
            mock_upload.return_value = {"url": "http://test.com/file.csv"}
            
            with patch('toklabel.minio_importer.export_urls_to_redis') as mock_redis:
                mock_redis.return_value = {"message": "Success"}
                
                result = importer.batch_import_csv_files(prefix="test_data")
                
                self.assertNotIn("error", result)
                self.assertEqual(len(result["imported_shots"]), 2)
                self.assertIn(240830026, result["imported_shots"])
                self.assertIn(240830027, result["imported_shots"])
    
    def test_minio_config_manager(self):
        """测试MinIO配置管理器"""
        config_manager = MinIOConfigManager(self.temp_config.name)
        
        # 测试启用MinIO
        result = config_manager.enable_minio(
            bucket="new-bucket",
            prefix="new_prefix",
            auto_sync=True
        )
        
        self.assertNotIn("error", result)
        self.assertTrue(config_manager.is_minio_enabled())
        
        # 测试创建管道配置
        pipeline_config = config_manager.create_data_pipeline_config(
            source_type="postgres",
            source_config={"shots": [1, 2, 3]},
            processors=[{"type": "filter", "config": {"condition": "time > 0"}}],
            destination_prefix="processed"
        )
        
        self.assertEqual(pipeline_config["source"]["type"], "postgres")
        self.assertEqual(len(pipeline_config["processors"]), 1)
    
    @patch('toklabel.minio_data_manager.upload_to_minio')
    def test_minio_data_manager_batch_process(self, mock_upload):
        """测试MinIO数据管理器批量处理"""
        mock_upload.return_value = {"message": "Success", "path": "test/path.csv"}
        
        data_manager = MinIODataManager(self.project_name, self.bucket_name)
        
        # 创建测试数据处理器
        def test_processor(shot: int) -> pd.DataFrame:
            return pd.DataFrame({
                'time': [1.0, 2.0, 3.0],
                'value': [shot * 10, shot * 20, shot * 30]
            })
        
        result = data_manager.batch_process_and_upload(
            data_processor=test_processor,
            shots=[1, 2, 3],
            prefix="test_prefix",
            max_workers=2
        )
        
        self.assertEqual(len(result["uploaded_files"]), 3)
        self.assertEqual(len(result["failed_files"]), 0)
    
    @patch('toklabel.minio_validator.download_from_minio')
    def test_minio_validator(self, mock_download):
        """测试MinIO数据验证器"""
        # 模拟有效的CSV内容
        valid_csv = "time,CS1,CS2\n1.0,10.0,20.0\n2.0,15.0,25.0\n"
        mock_download.return_value = valid_csv.encode('utf-8')
        
        validator = MinIODataValidator(self.project_name, self.bucket_name)
        
        with patch.object(validator.importer, 'list_available_files') as mock_list:
            mock_list.return_value = ["test_project/240830026.csv"]
            
            result = validator.validate_csv_files(
                prefix="test_project",
                required_columns=["time", "CS1", "CS2"]
            )
            
            self.assertNotIn("error", result)
            self.assertEqual(result["valid_files"], 1)
            self.assertEqual(result["invalid_files"], 0)

class TestMinIOWorkflow(unittest.TestCase):
    """MinIO工作流测试"""
    
    def setUp(self):
        """测试设置"""
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_content = """
project: workflow_test
minio:
  enabled: true
  bucket: workflow-bucket
  prefix: workflow_data
  auto_sync: true
pipelines:
  - source:
      type: postgres
      config:
        shots: [1, 2, 3]
    processors:
      - type: filter
        config:
          condition: "time > 0"
    destination:
      type: minio
      prefix: processed
"""
        self.temp_config.write(config_content)
        self.temp_config.close()
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.temp_config.name)
    
    @patch('toklabel.minio_workflow_manager.ProjectBuilder')
    @patch('toklabel.minio_workflow_manager.MinIODataManager')
    def test_workflow_manager_initialization(self, mock_data_manager, mock_project_builder):
        """测试工作流管理器初始化"""
        from toklabel.minio_workflow_manager import MinIOWorkflowManager
        
        # 模拟ProjectBuilder
        mock_pb_instance = MagicMock()
        mock_pb_instance.project = "workflow_test"
        mock_pb_instance.minio_enabled = True
        mock_pb_instance.minio_bucket = "workflow-bucket"
        mock_project_builder.return_value = mock_pb_instance
        
        # 创建工作流管理器
        workflow = MinIOWorkflowManager(self.temp_config.name)
        result = workflow.initialize_project()
        
        self.assertNotIn("error", result)
        self.assertEqual(result["project_name"], "workflow_test")
        self.assertTrue(result["minio_enabled"])

if __name__ == '__main__':
    unittest.main()

10. 创建MinIO部署配置

创建新文件 k8s/minio-deployment.yaml：

apiVersion: v1
kind: Namespace
metadata:
  name: minio-system
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: minio-pv
  namespace: minio-system
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-storage
  local:
    path: /data/minio
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - your-node-name
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-pvc
  namespace: minio-system
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: local-storage
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: minio-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
      - name: minio
        image: minio/minio:latest
        args:
        - server
        - /data
        - --console-address
        - ":9001"
        env:
        - name: MINIO_ROOT_USER
          value: "minioadmin"
        - name: MINIO_ROOT_PASSWORD
          value: "minioadmin"

Wiki pages you might want to explore:
- [System Architecture (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#1.1)
- [Development and Contributing (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#6)

好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 k8s/minio-deployment.yaml

        ports:
        - containerPort: 9000
        - containerPort: 9001
        volumeMounts:
        - name: minio-storage
          mountPath: /data
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2048Mi"
            cpu: "1000m"
      volumes:
      - name: minio-storage
        persistentVolumeClaim:
          claimName: minio-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: minio-service
  namespace: minio-system
spec:
  selector:
    app: minio
  ports:
  - name: api
    port: 9000
    targetPort: 9000
  - name: console
    port: 9001
    targetPort: 9001
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: minio-ingress
  namespace: minio-system
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/use-regex: "true"
spec:
  ingressClassName: nginx
  rules:
  - host: dap0.lan
    http:
      paths:
      - path: /minio(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: minio-service
            port:
              number: 9000
      - path: /minio-console(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: minio-service
            port:
              number: 9001

11. 创建MinIO与现有系统的集成脚本

创建新文件 scripts/setup_minio_integration.py：

#!/usr/bin/env python3
"""
MinIO集成设置脚本
"""

import os
import sys
import yaml
import argparse
from pathlib import Path

def setup_minio_environment(config_file: str, minio_endpoint: str, bucket_name: str):
    """设置MinIO环境配置"""
    
    # 1. 更新环境变量文件
    env_file = Path('.env')
    env_content = []
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.readlines()
    
    # 添加或更新MinIO配置
    minio_vars = {
        'STORAGE_BACKEND': 'minio',
        'MINIO_ENDPOINT': minio_endpoint,
        'MINIO_BUCKET': bucket_name,
        'MINIO_ACCESS_KEY': 'minioadmin',
        'MINIO_SECRET_KEY': 'minioadmin',
        'MINIO_SECURE': 'false'
    }
    
    # 更新或添加环境变量
    for var, value in minio_vars.items():
        found = False
        for i, line in enumerate(env_content):
            if line.startswith(f"{var}="):
                env_content[i] = f"{var}={value}\n"
                found = True
                break
        if not found:
            env_content.append(f"{var}={value}\n")
    
    with open(env_file, 'w') as f:
        f.writelines(env_content)
    
    print(f"✓ 已更新 {env_file} 文件")
    
    # 2. 更新项目配置文件
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # 添加MinIO配置
    config['minio'] = {
        'enabled': True,
        'bucket': bucket_name,
        'prefix': f"{config.get('project', 'default')}_data",
        'auto_sync': True,
        'import_pattern': r'/(\d+)\.csv$'
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"✓ 已更新 {config_file} 配置文件")
    
    # 3. 创建测试脚本
    test_script = Path('test_minio_connection.py')
    test_content = f"""#!/usr/bin/env python3
import os
from minio import Minio
from minio.error import S3Error

def test_minio_connection():
    try:
        client = Minio(
            '{minio_endpoint}',
            access_key='minioadmin',
            secret_key='minioadmin',
            secure=False
        )
        
        # 测试连接
        buckets = client.list_buckets()
        print(f"✓ MinIO连接成功，发现 {{len(buckets)}} 个存储桶")
        
        # 检查目标桶
        if client.bucket_exists('{bucket_name}'):
            print(f"✓ 存储桶 '{bucket_name}' 已存在")
        else:
            client.make_bucket('{bucket_name}')
            print(f"✓ 已创建存储桶 '{bucket_name}'")
        
        return True
        
    except S3Error as e:
        print(f"✗ MinIO S3错误: {{e}}")
        return False
    except Exception as e:
        print(f"✗ MinIO连接错误: {{e}}")
        return False

if __name__ == "__main__":
    success = test_minio_connection()
    sys.exit(0 if success else 1)
"""
    
    with open(test_script, 'w') as f:
        f.write(test_content)
    
    os.chmod(test_script, 0o755)
    print(f"✓ 已创建测试脚本 {test_script}")

def create_docker_compose_override():
    """创建Docker Compose覆盖文件"""
    
    override_content = """version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: tok-label-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - tok-label-network

  file-server:
    environment:
      - STORAGE_BACKEND=minio
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET=tok-label
      - MINIO_SECURE=false
    depends_on:
      - minio
    networks:
      - tok-label-network

volumes:
  minio_data:

networks:
  tok-label-network:
    driver: bridge
"""
    
    with open('docker-compose.minio.yml', 'w') as f:
        f.write(override_content)
    
    print("✓ 已创建 docker-compose.minio.yml 文件")

def main():
    parser = argparse.ArgumentParser(description='设置MinIO集成')
    parser.add_argument('--config', default='project-config.yaml', help='项目配置文件路径')
    parser.add_argument('--endpoint', default='localhost:9000', help='MinIO端点')
    parser.add_argument('--bucket', default='tok-label', help='MinIO存储桶名称')
    parser.add_argument('--docker', action='store_true', help='创建Docker Compose配置')
    
    args = parser.parse_args()
    
    print("=== MinIO集成设置 ===")
    
    # 设置环境
    setup_minio_environment(args.config, args.endpoint, args.bucket)
    
    # 创建Docker配置（如果需要）
    if args.docker:
        create_docker_compose_override()
    
    print("\n=== 设置完成 ===")
    print("请运行以下命令测试MinIO连接:")
    print("python test_minio_connection.py")
    
    if args.docker:
        print("\n启动MinIO服务:")
        print("docker-compose -f docker-compose.minio.yml up -d")

if __name__ == "__main__":
    main()

12. 创建MinIO数据迁移工具

创建新文件 scripts/migrate_to_minio.py：

#!/usr/bin/env python3
"""
数据迁移工具：从本地存储迁移到MinIO
"""

import os
import argparse
import pandas as pd
from pathlib import Path
from typing import List, Dict
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_local_files_to_minio(local_data_dir: str, minio_prefix: str = "", bucket: str = "tok-label") -> Dict:
    """
    将本地文件迁移到MinIO
    
    参数:
    local_data_dir: 本地数据目录
    minio_prefix: MinIO对象前缀
    bucket: 目标存储桶
    
    返回:
    Dict: 迁移结果
    """
    try:
        from toklabel.utils import upload_to_minio
        
        local_path = Path(local_data_dir)
        if not local_path.exists():
            return {"error": f"Local directory {local_data_dir} does not exist"}
        
        migrated_files = []
        failed_files = []
        
        # 递归查找所有文件
        for file_path in local_path.rglob('*'):
            if file_path.is_file():
                try:
                    # 计算相对路径
                    rel_path = file_path.relative_to(local_path)
                    minio_path = f"{minio_prefix}/{rel_path}" if minio_prefix else str(rel_path)
                    minio_path = minio_path.replace('\\', '/')  # 确保使用正斜杠
                    
                    # 读取文件内容
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # 上传到MinIO
                    result = upload_to_minio(minio_path, content, bucket)
                    
                    if result.get("error"):
                        failed_files.append({
                            "local_path": str(file_path),
                            "minio_path": minio_path,
                            "error": result["error"]
                        })
                    else:
                        migrated_files.append({
                            "local_path": str(file_path),
                            "minio_path": minio_path,
                            "size": len(content)
                        })
                        logger.info(f"Migrated: {rel_path} -> {minio_path}")
                    
                except Exception as e:
                    failed_files.append({
                        "local_path": str(file_path),
                        "error": str(e)
                    })
        
        return {
            "message": f"Migration completed: {len(migrated_files)} files migrated, {len(failed_files)} failed",
            "migrated_files": migrated_files,
            "failed_files": failed_files,
            "total_size": sum(f["size"] for f in migrated_files)
        }
        
    except Exception as e:
        return {"error": f"Migration error: {str(e)}"}

def migrate_redis_urls_to_minio(project_name: str, redis_key: str = "csv", bucket: str = "tok-label") -> Dict:
    """
    将Redis中的URL数据迁移到MinIO
    
    参数:
    project_name: 项目名称
    redis_key: Redis键名
    bucket: 目标存储桶
    
    返回:
    Dict: 迁移结果
    """
    try:
        from toklabel.utils import connect_redis, upload_to_minio
        import requests
        
        # 连接Redis
        redis_conn = connect_redis()
        redis_data_key = f"{project_name}/{redis_key}"
        
        # 获取Redis中的URL数据
        urls_data = redis_conn.get(redis_data_key)
        if not urls_data:
            return {"error": f"No data found in Redis for key: {redis_data_key}"}
        
        import json
        urls = json.loads(urls_data)
        
        migrated_shots = []
        failed_shots = []
        
        for shot, url in urls.items():
            try:
                # 下载文件内容
                response = requests.get(url)
                response.raise_for_status()
                content = response.content
                
                # 上传到MinIO
                minio_path = f"{project_name}/data/{shot}.csv"
                result = upload_to_minio(minio_path, content, bucket)
                
                if result.get("error"):
                    failed_shots.append({
                        "shot": shot,
                        "url": url,
                        "error": result["error"]
                    })
                else:
                    migrated_shots.append({
                        "shot": shot,
                        "original_url": url,
                        "minio_path": minio_path
                    })
                    logger.info(f"Migrated shot {shot} to MinIO")
                
            except Exception as e:
                failed_shots.append({
                    "shot": shot,
                    "url": url,
                    "error": str(e)
                })
        
        redis_conn.close()
        
        return {
            "message": f"Redis migration completed: {len(migrated_shots)} shots migrated, {len(failed_shots)} failed",
            "migrated_shots": migrated_shots,
            "failed_shots": failed_shots
        }
        
    except Exception as e:
        return {"error": f"Redis migration error: {str(e)}"}

def main():
    parser = argparse.ArgumentParser(description='数据迁移到MinIO')
    parser.add_argument('--local-dir', help='本地数据目录路径')
    parser.add_argument('--project', help='项目名称（用于Redis迁移）')
    parser.add_argument('--redis-key', default='csv', help='Redis键名')
    parser.add_argument('--bucket', default='tok-label', help='MinIO存储桶')

Wiki pages you might want to explore:
- [Kubernetes Deployment (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#3.1)
- [ML Backend Services (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#4)
- [Scientific Computing Services (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#4.2)

好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 scripts/migrate_to_minio.py

    parser.add_argument('--prefix', default='', help='MinIO对象前缀')
    parser.add_argument('--mode', choices=['local', 'redis', 'both'], default='both', help='迁移模式')
    
    args = parser.parse_args()
    
    print("=== MinIO数据迁移工具 ===")
    
    results = {}
    
    # 本地文件迁移
    if args.mode in ['local', 'both'] and args.local_dir:
        print(f"\n开始迁移本地目录: {args.local_dir}")
        local_result = migrate_local_files_to_minio(
            args.local_dir, 
            args.prefix, 
            args.bucket
        )
        results['local_migration'] = local_result
        print("本地迁移结果:", json.dumps(local_result, indent=2, ensure_ascii=False))
    
    # Redis数据迁移
    if args.mode in ['redis', 'both'] and args.project:
        print(f"\n开始迁移Redis项目: {args.project}")
        redis_result = migrate_redis_urls_to_minio(
            args.project,
            args.redis_key,
            args.bucket
        )
        results['redis_migration'] = redis_result
        print("Redis迁移结果:", json.dumps(redis_result, indent=2, ensure_ascii=False))
    
    # 输出总结
    print("\n=== 迁移完成 ===")
    total_migrated = 0
    total_failed = 0
    
    for migration_type, result in results.items():
        if not result.get("error"):
            if migration_type == 'local_migration':
                total_migrated += len(result.get("migrated_files", []))
                total_failed += len(result.get("failed_files", []))
            elif migration_type == 'redis_migration':
                total_migrated += len(result.get("migrated_shots", []))
                total_failed += len(result.get("failed_shots", []))
    
    print(f"总计迁移成功: {total_migrated} 个文件")
    print(f"总计迁移失败: {total_failed} 个文件")

if __name__ == "__main__":
    main()

13. 创建MinIO性能优化工具

创建新文件 toklabel/minio_performance.py：

import time
import asyncio
import aiohttp
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import upload_to_minio, download_from_minio
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MinIOPerformanceOptimizer:
    """MinIO性能优化器，提供并发上传下载和缓存功能"""
    
    def __init__(self, bucket: str = None, max_workers: int = 20):
        self.bucket = bucket
        self.max_workers = max_workers
        self.cache = {}
        
    def parallel_upload_dataframes(self, data_dict: Dict[str, pd.DataFrame], prefix: str = "") -> Dict:
        """
        并行上传多个DataFrame到MinIO
        
        参数:
        data_dict: {file_path: DataFrame} 字典
        prefix: MinIO对象前缀
        
        返回:
        Dict: 上传结果
        """
        def upload_single_df(item):
            file_path, df = item
            full_path = f"{prefix}/{file_path}" if prefix else file_path
            csv_content = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
            
            start_time = time.time()
            result = upload_to_minio(full_path, csv_content, self.bucket)
            upload_time = time.time() - start_time
            
            return {
                "file_path": full_path,
                "result": result,
                "upload_time": upload_time,
                "size": len(csv_content)
            }
        
        start_total = time.time()
        uploaded_files = []
        failed_files = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(upload_single_df, item): item for item in data_dict.items()}
            
            for future in as_completed(future_to_item):
                result = future.result()
                
                if result["result"].get("error"):
                    failed_files.append({
                        "file_path": result["file_path"],
                        "error": result["result"]["error"]
                    })
                else:
                    uploaded_files.append(result)
        
        total_time = time.time() - start_total
        total_size = sum(f["size"] for f in uploaded_files)
        
        return {
            "message": f"Parallel upload completed: {len(uploaded_files)} success, {len(failed_files)} failed",
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "performance": {
                "total_time": total_time,
                "total_size_mb": total_size / (1024 * 1024),
                "average_speed_mbps": (total_size / (1024 * 1024)) / total_time if total_time > 0 else 0
            }
        }
    
    def parallel_download_dataframes(self, file_paths: List[str], use_cache: bool = True) -> Dict:
        """
        并行下载多个文件并转换为DataFrame
        
        参数:
        file_paths: 文件路径列表
        use_cache: 是否使用缓存
        
        返回:
        Dict: 下载结果
        """
        def download_single_file(file_path):
            # 检查缓存
            if use_cache and file_path in self.cache:
                return {
                    "file_path": file_path,
                    "dataframe": self.cache[file_path],
                    "from_cache": True,
                    "download_time": 0
                }
            
            start_time = time.time()
            try:
                content = download_from_minio(file_path, self.bucket)
                from io import StringIO
                csv_string = content.decode('utf-8')
                df = pd.read_csv(StringIO(csv_string))
                
                # 添加到缓存
                if use_cache:
                    self.cache[file_path] = df
                
                download_time = time.time() - start_time
                
                return {
                    "file_path": file_path,
                    "dataframe": df,
                    "from_cache": False,
                    "download_time": download_time,
                    "size": len(content)
                }
                
            except Exception as e:
                return {
                    "file_path": file_path,
                    "error": str(e),
                    "download_time": time.time() - start_time
                }
        
        start_total = time.time()
        downloaded_data = {}
        failed_downloads = []
        cache_hits = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {executor.submit(download_single_file, path): path for path in file_paths}
            
            for future in as_completed(future_to_path):
                result = future.result()
                
                if "error" in result:
                    failed_downloads.append(result)
                else:
                    downloaded_data[result["file_path"]] = result["dataframe"]
                    if result["from_cache"]:
                        cache_hits += 1
        
        total_time = time.time() - start_total
        
        return {
            "message": f"Parallel download completed: {len(downloaded_data)} success, {len(failed_downloads)} failed",
            "downloaded_data": downloaded_data,
            "failed_downloads": failed_downloads,
            "performance": {
                "total_time": total_time,
                "cache_hits": cache_hits,
                "cache_hit_rate": cache_hits / len(file_paths) if file_paths else 0
            }
        }
    
    def clear_cache(self):
        """清理缓存"""
        self.cache.clear()
        logger.info("MinIO performance cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        total_memory = sum(df.memory_usage(deep=True).sum() for df in self.cache.values())
        
        return {
            "cached_files": len(self.cache),
            "total_memory_mb": total_memory / (1024 * 1024),
            "cached_file_paths": list(self.cache.keys())
        }

14. 创建完整的CLI工具

创建新文件 cli/minio_cli.py：

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

@cli.comman

好的，我来继续完成第二阶段的代码实现。<cite/>

继续完成 cli/minio_cli.py

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

15. 创建完整的README文档

创建新文件 docs/MINIO_INTEGRATION.md：

# MinIO集成指南

本文档介绍如何在TOKLABEL项目中集成和使用MinIO对象存储。

## 概述

MinIO集成提供了以下功能：
- 替代本地文件存储，使用MinIO作为后端存储
- 支持从MinIO批量导入数据到Label Studio
- 提供数据处理管道，支持PostgreSQL到MinIO的数据流
- 双向数据同步功能
- 完整的数据验证和监控工具

## 快速开始

### 1. 安装依赖

```bash
pip install minio>=7.1.0 click>=8.0.0

2. 配置MinIO

# 使用设置脚本
python scripts/setup_minio_integration.py --config project-config.yaml --endpoint localhost:9000 --bucket tok-label --docker

# 或手动配置环境变量
export STORAGE_BACKEND=minio
export MINIO_ENDPOINT=localhost:9000
export MINIO_BUCKET=tok-label
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin

3. 启动MinIO服务

# 使用Docker Compose
docker-compose -f docker-compose.minio.yml up -d

# 或使用Kubernetes
kubectl apply -f k8s/minio-deployment.yaml

4. 测试连接

python test_minio_connection.py

使用方法

命令行工具

# 启用MinIO集成
python cli/minio_cli.py enable --config project-config.yaml --bucket tok-label --auto-sync

# 从MinIO导入数据
python cli/minio_cli.py import-data --config project-config.yaml --prefix plasma_data

# 导出数据到MinIO
python cli/minio_cli.py export-data --config project-config.yaml --include-annotations

# 运行数据处理管道
python cli/minio_cli.py run-pipeline --config project-config.yaml --pipeline-index 0

# 健康检查
python cli/minio_cli.py health-check --bucket tok-label

# 数据验证
python cli/minio_cli.py validate --config project-config.yaml --required-columns time,CS1,CS2

# 数据迁移
python cli/minio_cli.py migrate --local-dir ./data --project plasma_analysis --mode both

Python API

import toklabel
from toklabel.minio_workflow_manager import MinIOWorkflowManager

# 1. 初始化工作流
workflow = MinIOWorkflowManager('project-config-minio.yaml')
workflow.initialize_project()

# 2. 连接Label Studio
ls = toklabel.connect_Label_Studio(API_key='your_api_key')

# 3. 运行完整工作流
result = workflow.run_complete_workflow(ls)

# 4. 运行数据管道
pipeline_result = workflow.run_data_pipeline(0)

# 5. 导出标注数据
annotation_result = workflow.export_and_store_annotations(ls, project_id, "annotations_table")

配置文件示例

参考 project-config-minio.yaml 获取完整的配置示例。

故障排除

常见问题

1. 连接失败: 检查MinIO端点和凭证配置
2. 上传失败: 检查存储桶权限和网络连接
3. 数据验证失败: 使用验证工具检查数据格式
  
日志查看

# 查看文件服务器日志
docker logs tok-label-file-server

# 查看MinIO日志
docker logs tok-label-minio

性能优化

- 使用并发上传/下载提高性能
- 启用数据缓存减少重复下载
- 合理配置max_workers参数
  
安全注意事项

- 在生产环境中使用强密码
- 启用HTTPS连接
- 配置适当的存储桶策略

### 16. 创建最终的集成测试脚本

创建新文件 `tests/integration_test_minio.py`：

```python
#!/usr/bin/env python3
"""
MinIO集成完整测试脚本
"""

import unittest
import tempfile
import os
import json
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestCompleteMinIOIntegration(unittest.TestCase):
    """完整的MinIO集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_content = """
project: integration_test
file_path: test_data
shots: [1, 2, 3]
minio:
  enabled: true
  bucket: test-bucket
  prefix: test_prefix
  auto_sync: true
pipelines:
  - source:
      type: postgres
      config:
        shots: [1, 2, 3]
        name_table_columns:
          test_table: ["test_table", ["col1", "col2"]]
    processors:
      - type: filter
        config:
          condition: "time > 0"
    destination:
      type: minio
      prefix: processed
"""
        self.test_config.write(config_content)
        self.test_config.close()
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.test_config.name)
    
    @patch('toklabel.utils.upload_to_minio')
    @patch('toklabel.utils.download_from_minio')
    @patch('toklabel.utils.list_minio_objects')
    def test_complete_workflow(self, mock_list, mock_download, mock_upload):
        """测试完整工作流"""
        # 模拟MinIO操作
        mock_list.return_value = ["test_prefix/integration_test/1.csv", "test_prefix/integration_test/2.csv"]
        mock_download.return_value = "time,col1,col2\n1.0,10,20\n2.0,15,25\n".encode('utf-8')
        mock_upload.return_value = {"message": "Success", "path": "test/path.csv"}
        
        from toklabel.minio_workflow_manager import MinIOWorkflowManager
        
        # 初始化工作流
        workflow = MinIOWorkflowManager(self.test_config.name)
        
        with patch.object(workflow, 'project_builder') as mock_pb:
            mock_pb.project = "integration_test"
            mock_pb.minio_enabled = True
            mock_pb.minio_bucket = "test-bucket"
            
            # 测试初始化
            result = workflow.initialize_project()
            self.assertNotIn("error", result)
            
            # 测试数据管道
            with patch.object(workflow, 'data_manager') as mock_dm:
                mock_dm.create_data_pipeline.return_value = {
                    "message": "Pipeline completed successfully",
                    "uploaded_files": [{"shot": 1}, {"shot": 2}]
                }
                
                pipeline_result = workflow.run_data_pipeline(0)
                self.assertNotIn("error", pipeline_result)
    
    def test_performance_optimization(self):
        """测试性能优化功能"""
        from toklabel.minio_performance import MinIOPerformanceOptimizer
        
        optimizer = MinIOPerformanceOptimizer(bucket="test-bucket", max_workers=5)
        
        # 测试缓存统计
        cache_stats = optimizer.get_cache_stats()
        self.assertEqual(cache_stats["cached_files"], 0)
        
        # 测试缓存清理
        optimizer.clear_cache()
        self.assertEqual(len(optimizer.cache), 0)

if __name__ == '__main__':
    # 运行所有测试
    unittest.main(verbosity=2)

17. 创建最终的requirements更新

更新 requirements.txt 文件：

# 现有依赖保持不变，添加以下MinIO相关依赖
minio>=7.1.0
fastapi>=0.68.0
uvicorn>=0.15.0
python-multipart>=0.0.5
click>=8.0.0
aiohttp>=3.8.0
pyyaml>=6.0
pandas>=1.3.0
redis>=4.0.0
requests>=2.25.0

18. 创建最终的使用文档

创建新文件 examples/README_MINIO.md：

# MinIO集成使用示例

## 基本使用流程

### 1. 完整工作流示例

```python
# examples/complete_minio_workflow.py
python examples/complete_minio_workflow.py

2. 高级管道配置

# examples/advanced_pipeline_example.py
python examples/advanced_pipeline_example.py

3. 批量数据处理

from toklabel.minio_data_manager import MinIODataManager

data_manager = MinIODataManager("your_project")

# 定义数据处理函数
def process_shot_data(shot: int):
    # 从PostgreSQL获取数据
    # 进行数据处理
    # 返回处理后的DataFrame
    pass

# 批量处理并上传
result = data_manager.batch_process_and_upload(
    data_processor=process_shot_data,
    shots=[1, 2, 3, 4, 5],
    prefix="processed_data",
    max_workers=10
)

配置示例

项目配置文件

参考 `project-

Wiki pages you might want to explore:
- [Kubernetes Deployment (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#3.1)
- [Scientific Computing Services (STARTORUS/tok-label)](/wiki/STARTORUS/tok-label#4.2)