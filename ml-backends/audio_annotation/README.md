# Audio Annotation ML Backend

这是一个专门用于音频标注的ML Backend，支持语音识别、音频分类等功能。

## 功能特性

- **语音识别**: 使用Whisper模型进行语音转文字
- **音频分类**: 区分语音、音乐、噪音等音频类型
- **多格式支持**: 支持WAV、MP3、M4A、FLAC、OGG等音频格式
- **实时预测**: 基于Label Studio ML Backend架构的实时预测服务

## 快速开始

### 使用Docker运行 (推荐)

1. 启动ML Backend服务:

```bash
docker-compose up
```

2. 验证服务运行状态:
  
```bash
curl http://localhost:9090/
# 返回: {"status":"UP"}
```

3. 在Label Studio中连接后端: 
   进入项目设置 -> Machine Learning -> Add Model，指定URL为 `http://localhost:9090`

### 从源码构建

```bash
docker-compose build
```

### 不使用Docker运行

```bash
python -m venv audio-ml-backend
source audio-ml-backend/bin/activate  # Windows: audio-ml-backend\Scripts\activate
pip install -r requirements.txt
python _wsgi.py
```

## 配置参数

在 `docker-compose.yml` 中可以设置以下参数:

- `BASIC_AUTH_USER` - 基础认证用户名
- `BASIC_AUTH_PASS` - 基础认证密码
- `LOG_LEVEL` - 日志级别
- `WORKERS` - 工作进程数
- `THREADS` - 线程数
- `SAMPLE_RATE` - 音频采样率 (默认16000)
- `MAX_AUDIO_LENGTH` - 最大音频长度(秒)

## Label Studio配置

在Label Studio中使用以下XML配置来支持音频标注:

```xml
<View>
  <Audio name="audio" value="$audio"/>
  <TextArea name="transcription" toName="audio" 
            placeholder="语音转文字结果"/>
  <Choices name="audio_type" toName="audio">
    <Choice value="语音"/>
    <Choice value="音乐"/>
    <Choice value="噪音"/>
  </Choices>
</View>
```

## 部署到Kubernetes

```bash
kubectl apply -f audio-annotation.yaml
```

## 自定义模型

可以通过修改 `audio_predictor.py` 中的模型来自定义音频处理逻辑。支持的模型包括:

- Whisper (语音识别)
- wav2vec2 (音频分类)
- 自定义音频分析模型

## 测试

运行测试确保功能正常:

```bash
pytest test_audio_backend.py -v
```

## 故障排除

### 常见问题

1. **模型加载失败**: 检查网络连接和模型下载权限
2. **音频处理错误**: 确认音频文件格式和大小
3. **内存不足**: 调整Docker容器的内存限制

### 日志查看

```bash
# Docker日志
docker logs audio-annotation-ml-backend

# Kubernetes日志
kubectl logs -f deployment/ml-backend-audio-annotation -n label-studio
```

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 许可证

本项目采用MIT许可证。
