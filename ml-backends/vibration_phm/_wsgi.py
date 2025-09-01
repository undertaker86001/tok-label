import os
import sys
from label_studio_ml.server import init_app
from model import VibrationPHMModel

# 设置环境变量
os.environ.setdefault('LABEL_STUDIO_ML_BACKEND_V2', 'true')

# 创建应用
app = init_app(
    model_class=VibrationPHMModel,
    model_dir=os.path.dirname(__file__),
    redis_queue=os.environ.get('RQ_QUEUE_NAME', 'default'),
    redis_host=os.environ.get('REDIS_HOST', 'localhost'),
    redis_port=int(os.environ.get('REDIS_PORT', 6379)),
    redis_db=int(os.environ.get('REDIS_DB', 0))
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "_wsgi:app",
        host="0.0.0.0",
        port=int(os.environ.get('ML_BACKEND_PORT', 9090)),
        workers=int(os.environ.get('ML_BACKEND_WORKERS', 1)),
        reload=False
    )
