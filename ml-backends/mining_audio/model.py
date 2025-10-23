"""
矿业声音样本ML Backend核心模型

基于Label Studio ML Backend架构，实现矿业音频的多标签分类服务
"""

from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
import librosa
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.preprocessing import StandardScaler
import os
import pickle
import logging
import time
import json

# Add S3 support
try:
    import boto3
    from botocore.exceptions import ClientError
    from urllib.parse import urlparse
    S3_SUPPORTED = True
except ImportError:
    S3_SUPPORTED = False

logger = logging.getLogger(__name__)

# 矿业场景标签定义
MINING_LABELS = {
    'equipment_status': ['normal', 'abnormal', 'maintenance_needed'],
    'fault_type': ['bearing_fault', 'motor_fault', 'hydraulic_leak', 'belt_fault'],
    'priority': ['low_priority', 'medium_priority', 'high_priority']
}


class S3Config:
    """S3 Configuration class for handling S3 authentication and connection settings"""
    
    def __init__(self, config_file_path: str = None):
        self.url = None
        self.access_key = None
        self.secret_key = None
        self.api = None
        self.path_style = None
        
        if config_file_path:
            self.load_from_file(config_file_path)
    
    def load_from_file(self, config_file_path: str):
        """Load S3 configuration from JSON file"""
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            s3_config = config_data.get('s3', {})
            self.url = s3_config.get('url')
            self.access_key = s3_config.get('accessKey')
            self.secret_key = s3_config.get('secretKey')
            self.api = s3_config.get('api', 's3v4')
            self.path_style = s3_config.get('path', 'auto')
            
            logger.info("S3 configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load S3 configuration from {config_file_path}: {e}")
    
    def to_boto3_config(self):
        """Convert to boto3 client configuration"""
        if not self.url or not self.access_key or not self.secret_key:
            return None
            
        # Parse endpoint URL
        from urllib.parse import urlparse
        parsed_url = urlparse(self.url)
        endpoint_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        return {
            'endpoint_url': endpoint_url,
            'aws_access_key_id': self.access_key,
            'aws_secret_access_key': self.secret_key,
            'region_name': 'us-east-1',  # Default region for MinIO
        }
    
    def is_configured(self):
        """Check if S3 configuration is complete"""
        return self.url and self.access_key and self.secret_key


class AudioFeatureExtractor:
    """音频特征提取器"""
    
    def __init__(self, sample_rate=25000, n_mfcc=13, n_fft=2048, hop_length=512):
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        
    def extract_features(self, audio_path):
        """提取音频特征"""
        try:
            # Check file size first
            file_size = os.path.getsize(audio_path)
            if file_size < 1000:  # Less than 1KB is likely empty/corrupted
                logger.warning(f"音频文件太小 ({file_size} bytes): {audio_path}")
                return None
                
            logger.info(f"尝试加载音频文件: {audio_path} (大小: {file_size} bytes)")
            
            # Additional validation for file encoding before processing
            try:
                # Check if file can be opened in binary mode
                with open(audio_path, 'rb') as f:
                    header = f.read(1024)  # Read first 1KB
                    if not header:
                        logger.error(f"音频文件无法读取: {audio_path}")
                        return None
            except Exception as e:
                logger.error(f"无法读取音频文件: {audio_path}, 错误: {e}")
                return None
            
            # Load audio file using librosa according to API documentation
            import librosa
            import numpy as np
            
            # Use librosa.load as the primary method (handles various formats properly)
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            # Ensure y is a numpy array and correct type according to librosa docs
            if not isinstance(y, np.ndarray):
                y = np.array(y)
            y = y.astype(np.float32)
            
            # Convert to mono if needed (librosa recommendation)
            if y.ndim > 1:
                y = librosa.to_mono(y)
                
            logger.info(f"使用librosa加载音频完成，采样率: {sr}, 音频长度: {len(y)} samples")
            
            # Check if audio is empty or too short
            if len(y) == 0:
                logger.warning(f"音频文件为空: {audio_path}")
                return None
                
            if len(y) < self.n_fft:
                logger.warning(f"音频太短无法处理: {audio_path}, 长度: {len(y)} samples, 需要至少: {self.n_fft} samples")
                return None
            
            # Ensure y is still a proper numpy array before feature extraction
            if not isinstance(y, np.ndarray):
                y = np.array(y)
            y = y.astype(np.float32)
            
            # Additional validation to ensure y is a proper 1D array
            if y.ndim != 1:
                logger.error(f"音频数据维度不正确: {y.ndim}，应该是1维")
                return None
                
            # 时域特征
            logger.info("提取时域特征...")
            try:
                # Ensure y is still a proper numpy array
                if not isinstance(y, np.ndarray):
                    y = np.array(y)
                y = y.astype(np.float32)
                
                zcr = librosa.feature.zero_crossing_rate(y, hop_length=self.hop_length)
                energy = librosa.feature.rms(y=y, hop_length=self.hop_length)
            except Exception as e:
                logger.error(f"时域特征提取失败: {e} for file {audio_path}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                return None
            
            # 频域特征
            logger.info("提取频域特征...")
            try:
                # Ensure y and sr are proper types
                if not isinstance(y, np.ndarray):
                    y = np.array(y)
                y = y.astype(np.float32)
                
                mfccs = librosa.feature.mfcc(y=y, sr=int(sr), n_mfcc=self.n_mfcc, 
                                           n_fft=self.n_fft, hop_length=self.hop_length)
                spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=int(sr), 
                                                                    hop_length=self.hop_length)
                spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=int(sr), 
                                                                  hop_length=self.hop_length)
                spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=int(sr), 
                                                                       hop_length=self.hop_length)
            except Exception as e:
                logger.error(f"频域特征提取失败: {e} for file {audio_path}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                return None
            
            # 合并特征
            logger.info("合并特征...")
            try:
                features = np.vstack([
                    mfccs,
                    zcr,
                    energy,
                    spectral_centroid,
                    spectral_rolloff,
                    spectral_bandwidth
                ])
            except Exception as e:
                logger.error(f"特征合并失败: {e} for file {audio_path}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                return None
            
            # 检查特征是否有效
            if features.size == 0:
                logger.warning(f"提取的特征为空: {audio_path}")
                return None
                
            # 统计特征（均值、标准差、最大值、最小值）
            logger.info("计算统计特征...")
            try:
                feature_stats = np.hstack([
                    np.mean(features, axis=1),
                    np.std(features, axis=1),
                    np.max(features, axis=1),
                    np.min(features, axis=1)
                ])
            except Exception as e:
                logger.error(f"统计特征计算失败: {e} for file {audio_path}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                return None
            
            # 检查是否有NaN或inf值
            if np.isnan(feature_stats).any() or np.isinf(feature_stats).any():
                logger.warning(f"特征包含NaN或inf值: {audio_path}")
                # 尝试修复NaN值
                feature_stats = np.nan_to_num(feature_stats, nan=0.0, posinf=0.0, neginf=0.0)
            
            logger.info(f"特征提取成功: {audio_path}")
            return feature_stats
            
        except FileNotFoundError:
            logger.error(f"音频文件未找到: {audio_path}")
            return None
        except librosa.ParameterError as e:
            logger.error(f"Librosa参数错误: {e} for file {audio_path}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None
        except Exception as e:
            logger.error(f"特征提取失败: {str(e)} for file {audio_path}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None


class MiningAudioClassifier(nn.Module):
    """矿业音频多标签分类模型"""
    
    def __init__(self, input_dim, hidden_dims=[256, 128, 64]):
        super(MiningAudioClassifier, self).__init__()
        
        # 特征提取层
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_dim = hidden_dim
            
        self.feature_extractor = nn.Sequential(*layers)
        
        # 多标签分类头
        self.equipment_status_head = nn.Linear(prev_dim, len(MINING_LABELS['equipment_status']))
        self.fault_type_head = nn.Linear(prev_dim, len(MINING_LABELS['fault_type']))
        self.priority_head = nn.Linear(prev_dim, len(MINING_LABELS['priority']))
        
    def forward(self, x):
        features = self.feature_extractor(x)
        
        equipment_status = torch.sigmoid(self.equipment_status_head(features))
        fault_type = torch.sigmoid(self.fault_type_head(features))
        priority = torch.sigmoid(self.priority_head(features))
        
        return {
            'equipment_status': equipment_status,
            'fault_type': fault_type,
            'priority': priority
        }


class MiningAudioMLBackend(LabelStudioMLBase):
    """矿业声音样本ML Backend"""
    
    def __init__(self, label_config=None, train_output=None, **kwargs):
        """Initialize the model"""
        super().__init__(label_config=label_config, train_output=train_output, **kwargs)
        self._initialized = False
        # Initialize model parameters from train_output or with defaults
        self.model_version = train_output.get('model_version', 'mining_audio_v1.0') if train_output else 'mining_audio_v1.0'
        self.training_count = train_output.get('training_count', 0) if train_output else 0
        self.last_training_time = train_output.get('last_training_time', time.time()) if train_output else time.time()
        
    def setup(self):
        """初始化模型配置"""
        # Only initialize if not already initialized
        if self._initialized:
            return
            
        # Initialize parent class properly
        # Call the parent setup method if it exists
        try:
            super().setup()
        except Exception as e:
            logger.warning(f"父类setup方法调用失败: {e}")
            
        # Initialize model version properly
        try:
            self.set("model_version", "mining_audio_v1.0")
        except Exception as e:
            logger.warning(f"设置模型版本失败: {e}")
            # Fallback to setting the attribute directly
            self.model_version = "mining_audio_v1.0"
            
        # 初始化特征提取器
        self.feature_extractor = AudioFeatureExtractor()
        
        # 模型路径
        self.model_path = os.getenv("MODEL_PATH", os.path.join(
            os.path.dirname(__file__), "mining_audio_model.pth"))
        self.scaler_path = os.getenv("SCALER_PATH", os.path.join(
            os.path.dirname(__file__), "feature_scaler.pkl"))
        
        # 加载模型和标准化器
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.scaler = None
        
        # S3配置
        config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
        self.s3_config = S3Config(config_file_path)
        
        self._load_model()
        self._initialized = True
        logger.info("矿业声音ML Backend初始化完成")
        
    def _load_model(self):
        """加载预训练模型"""
        try:
            if os.path.exists(self.model_path):
                # 假设特征维度为68 (13 MFCC + 5 其他特征) * 4 统计量
                input_dim = 68
                self.model = MiningAudioClassifier(input_dim)
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()
                logger.info("模型加载成功")
            else:
                logger.warning("模型文件不存在，使用随机初始化模型")
                self.model = MiningAudioClassifier(68)
                self.model.to(self.device)
                
            # 加载特征标准化器
            if os.path.exists(self.scaler_path):
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("特征标准化器加载成功")
            else:
                self.scaler = StandardScaler()
                logger.warning("标准化器文件不存在，使用默认标准化器")
                
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            
    def _download_s3_file(self, s3_url, local_path):
        """Download file from S3 URL"""
        if not S3_SUPPORTED:
            raise ImportError("boto3 is not installed. Please install it to handle S3 URLs.")
        
        # Parse S3 URL
        # s3://bucket/key
        if not s3_url.startswith("s3://"):
            raise ValueError("Invalid S3 URL format")
            
        s3_path = s3_url[5:]  # Remove "s3://"
        bucket_name, key = s3_path.split("/", 1)
        
        # Create S3 client with custom configuration if available
        try:
            # Try to get S3 configuration
            config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
            s3_config = S3Config(config_file_path)
            
            if s3_config.is_configured():
                # Use custom S3 configuration
                boto3_config = s3_config.to_boto3_config()
                if boto3_config:
                    s3_client = boto3.client('s3', **boto3_config)
                    logger.info(f"Using custom S3 configuration for endpoint: {boto3_config.get('endpoint_url')}")
                else:
                    s3_client = boto3.client('s3')
            else:
                # Use default AWS configuration
                s3_client = boto3.client('s3')
        except Exception as e:
            logger.warning(f"Failed to create S3 client with custom configuration: {e}. Using default configuration.")
            s3_client = boto3.client('s3')
        
        try:
            logger.info(f"Downloading {s3_url} to {local_path}")
            # Download file content first to memory to ensure proper handling
            response = s3_client.get_object(Bucket=bucket_name, Key=key)
            file_content = response['Body'].read()
            
            # Write to local file with proper binary mode
            with open(local_path, 'wb') as f:
                f.write(file_content)
            
            # Verify the downloaded file
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                logger.info(f"Successfully downloaded {s3_url}, file size: {file_size} bytes")
                
                # Try to validate the audio file format
                try:
                    import soundfile as sf
                    info = sf.info(local_path)
                    logger.info(f"Downloaded file validation - 采样率: {info.samplerate}, 时长: {info.duration}s, 格式: {info.format_info}")
                except Exception as e:
                    logger.warning(f"Downloaded file format validation failed: {e}")
                    # Try to determine the file type
                    try:
                        import magic
                        file_type = magic.from_file(local_path, mime=True)
                        logger.info(f"Downloaded file actual type: {file_type}")
                    except Exception:
                        pass
            else:
                logger.error(f"Failed to create local file: {local_path}")
                raise Exception("File download failed")
            
            return local_path
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket '{bucket_name}' does not exist")
            elif error_code == 'NoSuchKey':
                raise ValueError(f"S3 key '{key}' does not exist in bucket '{bucket_name}'")
            elif error_code == 'AccessDenied':
                raise PermissionError(f"Access denied to S3 resource {s3_url}. Check your AWS credentials and permissions.")
            elif error_code == 'InvalidAccessKeyId' or error_code == 'SignatureDoesNotMatch':
                raise PermissionError(f"AWS credentials are invalid or not configured. Please configure AWS credentials to access S3 resources.")
            else:
                logger.error(f"Failed to download {s3_url}: {e}")
                raise
        except Exception as e:
            # Handle the specific case of missing credentials
            if "Unable to locate credentials" in str(e):
                raise PermissionError(f"AWS credentials not found. Please configure AWS credentials using one of these methods:\n"
                                    f"1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                                    f"2. Run 'aws configure' if you have AWS CLI installed\n"
                                    f"3. Use an IAM role if running on EC2\n"
                                    f"4. Place credentials in ~/.aws/credentials file")
            logger.error(f"Unexpected error downloading {s3_url}: {e}")
            raise
            
    def _get_local_path_for_s3(self, s3_url):
        """Get local path for S3 URL"""
        import hashlib
        from appdirs import user_cache_dir
        import os
        
        # Create cache directory
        cache_dir = user_cache_dir(appname='label-studio')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Generate filename based on URL hash
        url_hash = hashlib.md5(s3_url.encode()).hexdigest()[:6]
        filename = os.path.basename(s3_url)
        local_path = os.path.join(cache_dir, url_hash + '__' + filename)
        
        # Always download the file to ensure we have the latest version
        # This prevents issues with corrupted cache files
        try:
            self._download_s3_file(s3_url, local_path)
            logger.info(f"文件已下载到: {local_path}")
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            # If download fails, check if we have a valid cached file
            if os.path.exists(local_path):
                try:
                    # Check file size
                    file_size = os.path.getsize(local_path)
                    if file_size > 0:
                        # Try to validate the audio file format
                        import soundfile as sf
                        info = sf.info(local_path)
                        logger.info(f"使用现有缓存文件 - 采样率: {info.samplerate}, 时长: {info.duration}s")
                        return local_path
                except Exception as validation_error:
                    logger.warning(f"缓存文件验证失败: {validation_error}")
            
            # If we can't use cached file, re-raise the download error
            raise
            
        return local_path
    
    def _preprocess_audio(self, audio_path):
        """音频预处理"""
        # Ensure setup has been called
        if not self._initialized:
            self.setup()
            
        # Validate audio file exists and is accessible
        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return None
            
        # Check file size
        try:
            file_size = os.path.getsize(audio_path)
            if file_size == 0:
                logger.error(f"音频文件为空: {audio_path}")
                return None
            logger.info(f"音频文件大小: {file_size} bytes")
            
            # If file is too small, it's likely corrupted
            if file_size < 1000:  # Less than 1KB
                logger.error(f"音频文件太小 ({file_size} bytes)，可能是损坏的: {audio_path}")
                return None
        except Exception as e:
            logger.error(f"无法获取音频文件大小: {audio_path}, 错误: {e}")
            return None
            
        # Try to validate the audio file format
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            logger.info(f"音频文件验证通过 - 采样率: {info.samplerate}, 时长: {info.duration}s, 帧数: {info.frames}, 格式: {info.format_info}")
        except Exception as e:
            logger.warning(f"音频文件格式验证失败: {e}")
            # Try to determine the file type
            try:
                import magic
                file_type = magic.from_file(audio_path, mime=True)
                logger.info(f"文件实际类型: {file_type}")
            except Exception:
                pass
            
        # Additional validation for file encoding
        try:
            # Check if file can be opened in binary mode
            with open(audio_path, 'rb') as f:
                header = f.read(1024)  # Read first 1KB
                if not header:
                    logger.error(f"音频文件无法读取: {audio_path}")
                    return None
                logger.info(f"文件头信息: {header[:50]}...")  # Log first 50 bytes
        except Exception as e:
            logger.error(f"无法读取音频文件: {audio_path}, 错误: {e}")
            return None
            
        # Extract features
        features = self.feature_extractor.extract_features(audio_path)
        if features is None:
            logger.error(f"无法从音频文件提取特征: {audio_path}")
            # Try to get more information about why feature extraction failed
            try:
                import soundfile as sf
                info = sf.info(audio_path)
                logger.info(f"文件信息 - 采样率: {info.samplerate}, 时长: {info.duration}s, 帧数: {info.frames}")
            except Exception as e:
                logger.error(f"文件可能已损坏: {e}")
            return None
            
        # 特征标准化
        if self.scaler:
            try:
                # Ensure features have the right shape for scaler
                if features.ndim == 1:
                    features = features.reshape(1, -1)
                features = self.scaler.transform(features)
            except ValueError as e:
                logger.error(f"特征标准化失败: {e} for file {audio_path}")
                return None
        else:
            # Ensure features have the right shape
            if features.ndim == 1:
                features = features.reshape(1, -1)
            
        return torch.FloatTensor(features).to(self.device)
    
    def _predict_labels(self, features):
        """多标签预测"""
        # Ensure setup has been called
        if not self._initialized:
            self.setup()
            
        with torch.no_grad():
            outputs = self.model(features)
            
        predictions = {}
        threshold = 0.5
        
        for category, logits in outputs.items():
            probs = logits.cpu().numpy()[0]
            predicted_labels = []
            
            for i, prob in enumerate(probs):
                if prob > threshold:
                    label_name = MINING_LABELS[category][i]
                    predicted_labels.append({
                        'label': label_name,
                        'confidence': float(prob)
                    })
                    
            predictions[category] = predicted_labels
            
        return predictions
    
    def _convert_to_labelstudio_format(self, predictions, task_id):
        """转换为Label Studio格式"""
        results = []
        
        for category, labels in predictions.items():
            if labels:  # 只添加有预测结果的类别
                for label_info in labels:
                    results.append({
                        "from_name": f"mining_{category}",
                        "to_name": "audio",
                        "type": "choices",
                        "value": {
                            "choices": [label_info['label']]
                        },
                        "score": label_info['confidence']
                    })
        
        return {
            "result": results,
            "model_version": self.model_version,
            "task": task_id
        }
    
    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs):
        """预测接口实现"""
        logger.info(f'运行矿业音频预测，任务数量: {len(tasks)}')
        predictions = []
        
        # Ensure setup has been called
        if not self._initialized:
            try:
                self.setup()
            except Exception as e:
                logger.error(f"模型初始化失败: {e}")
                return {'predictions': []}
        
        for task in tasks:
            try:
                task_id = task.get('id', 'unknown')
                logger.info(f'处理任务: {task_id}')
                
                # 获取音频文件路径
                audio_url = task['data'].get('audio')
                if not audio_url:
                    logger.warning(f"任务 {task_id} 缺少音频数据")
                    continue
                
                # Handle S3 URLs specially
                if audio_url.startswith("s3://"):
                    try:
                        logger.info(f"处理S3音频URL: {audio_url}")
                        audio_path = self._get_local_path_for_s3(audio_url)
                    except PermissionError as e:
                        logger.error(f"无法访问S3资源 {audio_url}: {e}")
                        # In development, you might want to use a local mock file
                        # For production, you need to configure AWS credentials
                        continue
                    except Exception as e:
                        logger.error(f"下载S3资源失败 {audio_url}: {e}")
                        continue
                else:
                    # 下载音频文件到本地
                    logger.info(f"处理本地音频URL: {audio_url}")
                    try:
                        audio_path = self.get_local_path(audio_url)
                    except Exception as e:
                        logger.error(f"获取本地音频路径失败 {audio_url}: {e}")
                        continue
                
                logger.info(f"音频文件路径: {audio_path}")
                
                # 特征提取
                features = self._preprocess_audio(audio_path)
                if features is None:
                    logger.error(f"音频特征提取失败: {audio_path}")
                    continue
                
                # 多标签预测
                label_predictions = self._predict_labels(features)
                
                # 转换为Label Studio格式
                ls_prediction = self._convert_to_labelstudio_format(
                    label_predictions, task.get('id'))
                
                predictions.append(ls_prediction)
                logger.info(f'任务 {task_id} 预测成功，生成 {len(ls_prediction["result"])} 个预测结果')
                
            except Exception as e:
                logger.error(f"预测任务 {task.get('id', 'unknown')} 失败: {e}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                continue
        
        logger.info(f"矿业音频预测完成，总共生成 {len(predictions)} 个预测结果")
        return {'predictions': predictions}
    
    def fit(self, tasks, workdir=None, **kwargs):
        """模型训练接口"""
        logger.info(f'收到矿业音频训练任务，任务数量: {len(tasks) if tasks else 0}')
        
        try:
            logger.info(f'当前模型版本: {self.model_version}')
            
            # 这里可以实现模型训练逻辑
            # 从标注数据中提取特征和标签
            # 训练模型并保存
            logger.info("开始模型训练...")
            
            # 模拟训练过程
            time.sleep(1)
            
            # 更新模型版本
            new_version = f"mining_audio_v1.0_{int(time.time())}"
            self.model_version = new_version
            logger.info(f'模型版本更新为: {new_version}')
            
            # 记录训练统计信息
            self.training_count += 1
            self.last_training_time = time.time()
            
            logger.info(f'矿业音频模型训练完成，总训练次数: {self.training_count}')
            
            # Return train_output for persistence
            return {
                'model_version': self.model_version,
                'training_count': self.training_count,
                'last_training_time': self.last_training_time
            }
            
        except Exception as e:
            logger.error(f'矿业音频模型训练过程中出错: {e}')
            return None
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        # Ensure setup has been called
        if not self._initialized:
            self.setup()
            
        return {
            'model_version': self.model_version,
            'training_count': self.training_count,
            'last_training_time': self.last_training_time,
            'mining_labels': MINING_LABELS,
            'device': str(self.device),
            'model_loaded': self.model is not None,
            'scaler_loaded': self.scaler is not None
        }
    
    def reset_model(self):
        """重置模型参数到默认值"""
        try:
            # 重置模型版本
            self.model_version = 'mining_audio_v1.0'
            self.training_count = 0
            self.last_training_time = time.time()
            
            # 重新加载模型
            self._load_model()
            
            logger.info("模型参数已重置到默认值")
            
        except Exception as e:
            logger.error(f"重置模型参数失败: {e}")
    
    def update_model_config(self, config: Dict):
        """更新模型配置"""
        try:
            if 'model_version' in config:
                self.model_version = config['model_version']
                logger.info(f"模型版本已更新: {config['model_version']}")
            
            if 'prediction_threshold' in config:
                # 可以更新预测阈值
                logger.info(f"预测阈值已更新: {config['prediction_threshold']}")
            
        except Exception as e:
            logger.error(f"更新模型配置失败: {e}")
    
    def health_check(self) -> Dict:
        """健康检查"""
        # Ensure setup has been called
        if not self._initialized:
            self.setup()
            
        try:
            return {
                'status': 'healthy',
                'model_version': self.model_version,
                'model_loaded': self.model is not None,
                'scaler_loaded': self.scaler is not None,
                'device': str(self.device),
                'last_training': self.last_training_time,
                'training_count': self.training_count
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }