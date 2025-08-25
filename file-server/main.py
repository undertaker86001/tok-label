from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from typing import Optional
from pydantic import BaseModel
from util import export_postgres_data
from doris_util import export_doris_data  # 新增 Doris 支持
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "/data"
URL_PREFIX = "/files"

# 挂载静态文件目录，使其可通过 URL 访问
app.mount(URL_PREFIX, StaticFiles(directory=DATA_DIR, html=True), name="files")

# 数据库类型配置
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'postgresql')  # 'postgresql' 或 'doris'

# 导出数据请求模型
class ExportRequest(BaseModel):
    project_name: str
    shots: int|list[int]
    name_table_columns: dict
    t_min: float = -np.inf
    t_max: float = np.inf
    resolution: float = 1e-3
    database_type: Optional[str] = None  # 新增：可选的数据库类型参数

# 统一的数据导出接口
@app.post("/export/")
async def export_data(request: ExportRequest):
    """
    统一的数据导出接口，支持 PostgreSQL 和 Doris
    """
    if isinstance(request.shots, int):
        request.shots = [request.shots]
    
    # 确定使用的数据库类型
    db_type = request.database_type or DATABASE_TYPE
    
    try:
        # 根据数据库类型选择对应的导出函数
        if db_type.lower() == 'doris':
            data = export_doris_data(
                request.shots, 
                request.name_table_columns, 
                request.t_min, 
                request.t_max, 
                request.resolution
            )
        else:
            # 默认使用 PostgreSQL
            data = export_postgres_data(
                request.shots, 
                request.name_table_columns, 
                request.t_min, 
                request.t_max, 
                request.resolution
            )
        
        # 保存数据到 CSV
        os.makedirs(os.path.join(DATA_DIR, request.project_name), exist_ok=True)
        successful_shots = []
        
        for shot in request.shots:
            if shot in data and not data[shot].empty:
                file_name = f"{request.project_name}/{shot}.csv"
                data[shot].to_csv(os.path.join(DATA_DIR, file_name), index=False, encoding='utf-8')
                successful_shots.append(shot)
            else:
                print(f"警告: 炮号 {shot} 没有数据或数据为空")
        
        # 返回成功导出的文件 URL
        return {
            "message": f"Data exported successfully from {db_type}", 
            "database_type": db_type,
            "successful_shots": successful_shots,
            "urls": [f"{URL_PREFIX}/{request.project_name}/{shot}.csv" for shot in successful_shots]
        }
        
    except Exception as e:
        return {
            "error": f"Failed to export data from {db_type}: {str(e)}",
            "database_type": db_type,
            "successful_shots": [],
            "urls": []
        }

# 列出文件接口保持不变
@app.get("/list/")
async def list_files(dir: str = None, recursive: bool = False):
    """
    列出 DATA_DIR (/data) 下的文件。

    参数
    ----
    dir        : 相对目录；None = /data 根目录
    recursive  : True 时递归列出子目录文件
    """
    base_path = os.path.join(DATA_DIR, dir) if dir else DATA_DIR

    if not os.path.exists(base_path):
        return {"error": f"Directory {dir or '/'} not found"}

    files_rel: list[str] = []
    # 是否递归查找
    if recursive:
        # os.walk 返回 (root, dirs, files)
        for root, _, filenames in os.walk(base_path):
            rel_root = os.path.relpath(root, DATA_DIR)  # 相对 DATA_DIR 的root
            for fname in filenames:
                # 拼出相对 DATA_DIR 的路径
                rel_path = os.path.join(rel_root, fname) if rel_root != "." else fname
                files_rel.append(rel_path)
    else:
        files_rel = os.listdir(base_path)

    files_rel.sort()

    file_urls = [f"{URL_PREFIX}/{path}" for path in files_rel]
    return {"files": files_rel, "urls": file_urls}

# 删除文件接口保持不变
@app.delete("/delete/")
async def delete_file(dir: str, file: Optional[str]=None):
    target = os.path.join(DATA_DIR, dir)
    # 检查目录是否存在
    if not os.path.exists(target):
        return {"error": f"Directory {dir} not found"}
    if file is None:
        # 删除目录及目录下的所有文件
        shutil.rmtree(target)
        return {"message": f"Directory {dir} and all contents deleted successfully"}
    # 检查文件是否存在
    if not os.path.exists(os.path.join(target, file)):
        return {"error": f"File {file} not found"}
    # 删除文件
    os.remove(os.path.join(DATA_DIR, dir, file))
    return {"message": f"File {file} deleted successfully"}

# 上传文件接口保持不变
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), dir: str = None):
    """
    上传文件到指定目录
    
    参数:
    ----
    file: 上传的文件
    dir: 目标目录，相对于 DATA_DIR
    """
    try:
        # 确定目标目录
        target_dir = os.path.join(DATA_DIR, dir) if dir else DATA_DIR
        
        # 如果目录不存在，则创建
        os.makedirs(target_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(target_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 生成文件 URL
        relative_path = os.path.join(dir, file.filename) if dir else file.filename
        file_url = f"{URL_PREFIX}/{relative_path}"
        
        return {
            "message": f"File {file.filename} uploaded successfully", 
            "filename": file.filename,
            "url": file_url
        }
    except Exception as e:
        return {"error": f"Failed to upload file: {str(e)}"}

# 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "database_type": DATABASE_TYPE,
        "data_dir": DATA_DIR
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
