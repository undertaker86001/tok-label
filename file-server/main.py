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
    """
    下载文件端点，主要用于MinIO存储后端
    
    参数:
    file_path (str): 文件路径
    
    返回:
    Response: 文件内容或错误信息
    """
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
    """
    列出存储中的文件
    
    参数:
    dir (str, optional): 目录路径，None表示根目录
    recursive (bool): 是否递归列出子目录
    
    返回:
    Dict: 包含文件列表和URL的字典
    """
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
    """
    删除文件或目录
    
    参数:
    dir (str): 目录路径
    file (str, optional): 文件名，None表示删除整个目录
    
    返回:
    Dict: 操作结果
    """
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
    """
    上传文件到存储
    
    参数:
    file (UploadFile): 上传的文件
    
    返回:
    Dict: 上传结果，包含文件URL
    """
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
    """
    从PostgreSQL导出数据并保存到存储
    
    参数:
    request (ExportRequest): 导出请求参数
    
    返回:
    Dict: 导出结果，包含文件URL列表
    """
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
