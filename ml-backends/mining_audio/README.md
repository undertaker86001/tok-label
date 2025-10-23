# 矿业声音ML Backend

基于Label Studio ML Backend架构的矿业音频多标签分类服务，专门用于矿山设备的声音样本分析和故障诊断。

## 功能特性

### 🎯 核心功能
- **多标签分类**: 支持设备状态、故障类型、优先级三个维度的同时预测
- **音频特征提取**: 基于MFCC、频谱特征、时域特征的全面音频分析
- **深度学习模型**: 使用PyTorch实现的神经网络分类器
- **实时预测**: 支持音频文件的实时分析和预测

### 🏷️ 支持的标签类型

#### 设备状态 (Equipment Status)
- `normal`: 正常运行
- `abnormal`: 异常状态
- `maintenance_needed`: 需要维护

#### 故障类型 (Fault Type)
- `bearing_fault`: 轴承故障
- `motor_fault`: 电机故障
- `hydraulic_leak`: 液压泄漏
- `belt_fault`: 皮带故障

#### 优先级 (Priority)
- `low_priority`: 低优先级
- `medium_priority`: 中等优先级
- `high_priority`: 高优先级

### 🔧 技术特性
- **音频格式支持**: WAV, MP3, FLAC, M4A
- **采样率**: 支持16kHz, 22.05kHz, 44.1kHz等多种采样率
- **特征维度**: 68维特征向量 (MFCC + 频谱特征 + 统计特征)
- **模型架构**: 多层感知机 + BatchNorm + Dropout
- **设备支持**: CPU/GPU自适应

## 快速开始

### 环境要求
- Python 3.8+
- PyTorch 1.9+
- Label Studio ML 1.0+

### 安装依赖
```bash
# 安装基础依赖
pip install -r requirements-base.txt

# 安装完整依赖
pip install -r requirements.txt

# 安装测试依赖
pip install -r requirements-test.txt
```

### 启动服务
```bash
# 开发模式启动
python _wsgi.py --host 0.0.0.0 --port 9090 --debug

# 生产模式启动
python _wsgi.py --host 0.0.0.0 --port 9090
```

### 使用启动脚本启动服务
为了方便使用，我们提供了多种启动脚本：

**Windows批处理脚本:**
```cmd
start_service.bat
```

**PowerShell脚本:**
```powershell
start_service.ps1
```

**Python脚本:**
```bash
python start_service.py
```

### Docker部署
```bash
# 构建镜像
docker build -t mining-audio-ml-backend .

# 运行容器
docker run -p 9091:9090 mining-audio-ml-backend

# 使用Docker Compose
docker-compose up -d
```

## API接口

### 健康检查
```http
GET /health
```

**响应示例:**
```json
{
    "status": "healthy",
    "model_version": "mining_audio_v1.0",
    "model_loaded": true,
    "scaler_loaded": true,
    "device": "cpu",
    "last_training": 1640995200,
    "training_count": 0
}
```

### 模型信息
```http
GET /model/info
```

**响应示例:**
```json
{
    "model_version": "mining_audio_v1.0",
    "training_count": 0,
    "last_training_time": 1640995200,
    "mining_labels": {
        "equipment_status": ["normal", "abnormal", "maintenance_needed"],
        "fault_type": ["bearing_fault", "motor_fault", "hydraulic_leak", "belt_fault"],
        "priority": ["low_priority", "medium_priority", "high_priority"]
    },
    "device": "cpu",
    "model_loaded": true,
    "scaler_loaded": true
}
```

### 音频预测
```http
POST /predict
Content-Type: application/json

{
    "tasks": [
        {
            "data": {
                "audio": "path/to/audio.wav"
            }
        }
    ]
}
```

**响应示例:**
```json
{
    "predictions": [
        {
            "result": [
                {
                    "from_name": "mining_equipment_status",
                    "to_name": "audio",
                    "type": "choices",
                    "value": {
                        "choices": ["normal"]
                    },
                    "score": 0.85
                },
                {
                    "from_name": "mining_fault_type",
                    "to_name": "audio",
                    "type": "choices",
                    "value": {
                        "choices": ["bearing_fault"]
                    },
                    "score": 0.72
                }
            ],
            "model_version": "mining_audio_v1.0",
            "task": 1
        }
    ]
}
```

### 模型训练
```http
POST /fit
Content-Type: application/json

{
    "event": "START_TRAINING",
    "annotation": {
        "result": [
            {
                "from_name": "mining_equipment_status",
                "value": {
                    "choices": ["normal"]
                }
            }
        ]
    }
}
```

### 模型重置
```http
POST /model/reset
```

## 配置说明

### 配置文件 (config.json)
```json
{
    "model_version": "mining_audio_v1.0",
    "sample_rate": 22050,
    "n_mfcc": 13,
    "prediction_threshold": 0.5,
    "max_audio_length": 300,
    "supported_formats": ["wav", "mp3", "flac", "m4a"],
    "feature_extraction": {
        "n_fft": 2048,
        "hop_length": 512,
        "window": "hann"
    },
    "model_architecture": {
        "hidden_dims": [256, 128, 64],
        "dropout_rate": 0.3,
        "batch_norm": true
    }
}
```

### 环境变量
- `MODEL_PATH`: 模型文件路径
- `SCALER_PATH`: 特征标准化器路径
- `LOG_LEVEL`: 日志级别 (DEBUG/INFO/WARNING/ERROR)
- `PORT`: 服务端口 (默认: 9090)

## 测试

### 运行基础测试
```bash
# 运行所有测试
python test_mining_backend.py

# 使用pytest运行
pytest test_mining_backend.py -v
```

### 运行端到端测试
```bash
# 运行端到端测试
python test_e2e.py

# 使用pytest运行
pytest test_e2e.py -v --tb=short
```

### 测试覆盖率
```bash
pytest test_mining_backend.py --cov=model --cov-report=html
```

## 模型训练

### 训练脚本
```bash
python train_model.py --data_path data/mining_audio_dataset.csv --model_save_path models/mining_audio_model.pth
```

### 训练数据格式
CSV文件应包含以下列:
- `audio_path`: 音频文件路径
- `equipment_status`: 设备状态标签
- `fault_type`: 故障类型标签
- `priority`: 优先级标签

## 部署

### Kubernetes部署
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mining-audio-ml-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mining-audio-ml-backend
  template:
    metadata:
      labels:
        app: mining-audio-ml-backend
    spec:
      containers:
      - name: ml-backend
        image: mining-audio-ml-backend:latest
        ports:
        - containerPort: 9090
        env:
        - name: MODEL_PATH
          value: "/data/models/mining_audio_model.pth"
        - name: SCALER_PATH
          value: "/data/models/feature_scaler.pkl"
        volumeMounts:
        - name: model-storage
          mountPath: /data/models
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: mining-audio-models-pvc
```

### 负载均衡配置
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mining-audio-ml-backend-service
spec:
  selector:
    app: mining-audio-ml-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 9090
  type: LoadBalancer
```

## 监控和日志

### 日志格式
```
[2024-01-01 12:00:00] [INFO] [model::predict::123] 运行矿业音频预测，任务数量: 1
[2024-01-01 12:00:01] [INFO] [model::predict::145] 任务 1 预测成功，生成 2 个预测结果
```

### 性能指标
- 预测延迟: < 5秒 (10秒音频)
- 特征提取时间: < 2秒
- 模型推理时间: < 1秒
- 内存使用: < 2GB

## 故障排除

### 常见问题

#### 1. 音频加载失败
- 检查音频文件格式是否支持
- 确认文件路径是否正确
- 验证音频文件完整性

#### 2. 模型加载失败
- 检查模型文件路径
- 确认PyTorch版本兼容性
- 验证模型文件完整性

#### 3. 特征提取失败
- 检查librosa依赖是否正确安装
- 确认音频文件格式支持
- 验证采样率设置

### 调试模式
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
python _wsgi.py --debug

# 检查模型实例
python _wsgi.py --check
```
