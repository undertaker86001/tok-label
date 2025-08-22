# Temperature Annotation ML Backend

这是一个专门用于托卡马克等离子体温度数据标注的ML Backend，支持温度特征识别、异常检测和智能标注。

## 功能特性

- **温度特征识别**: 自动检测温度上升、下降、峰值等关键阶段
- **异常事件检测**: 识别温度突变、骤降等异常情况
- **多通道支持**: 支持多个温度测量通道的并行分析
- **自适应阈值**: 基于人工标注自动优化检测阈值
- **实时预测**: 基于Label Studio ML Backend架构的实时预测服务

## 核心算法

### 温度阶段检测
- **上升阶段**: 检测温度超过阈值的持续上升区间
- **峰值时刻**: 基于梯度变化检测温度峰值点
- **下降阶段**: 识别温度低于阈值的下降区间
- **平台期**: 检测温度相对稳定的平台阶段

### 异常检测
- **温度突变**: 基于滑动窗口统计检测异常温度变化
- **温度骤降**: 识别温度快速下降的异常事件

### 阈值优化
- 支持基于人工标注的自适应阈值调整
- 动态学习不同实验条件下的最佳参数

## 快速开始

### 使用Docker运行 (推荐)

1. 启动ML Backend服务:

```bash
docker-compose up
```

2. 验证服务运行状态:
  
```bash
curl http://localhost:9090/health
# 返回: {"status":"healthy","model_version":"temperature_v1.0",...}
```

3. 在Label Studio中连接后端: 
   进入项目设置 -> Machine Learning -> Add Model，指定URL为 `http://localhost:9090`

### 从源码构建

```bash
docker-compose build
```

### 不使用Docker运行

```bash
python -m venv temperature-ml-backend
source temperature-ml-backend/bin/activate  # Windows: temperature-ml-backend\Scripts\activate
pip install -r requirements.txt
python _wsgi.py
```

## 配置参数

在 `config.json` 中可以设置以下参数:

### 温度阈值设置
- `temp_rise_threshold`: 温度上升阈值 (默认1000.0 eV)
- `temp_fall_threshold`: 温度下降阈值 (默认500.0 eV)
- `gradient_threshold`: 梯度阈值 (默认100.0 eV/ms)
- `anomaly_threshold`: 异常检测阈值 (默认3.0)
- `min_peak_height`: 最小峰值高度 (默认800.0 eV)

### 数据处理设置
- `remove_outliers`: 是否移除异常值
- `outlier_threshold`: 异常值检测阈值
- `interpolate_missing`: 是否插值缺失值
- `normalize_data`: 是否标准化数据

### 预测设置
- `detect_rise_phases`: 是否检测上升阶段
- `detect_peak_moments`: 是否检测峰值时刻
- `detect_fall_phases`: 是否检测下降阶段
- `detect_anomalies`: 是否检测异常事件
- `detect_plateau_phases`: 是否检测平台期

## Label Studio配置

在Label Studio中使用以下XML配置来支持温度标注:

```xml
<View>
  <TimeSeries name="ts" value="$ts">
    <TimeSeriesLabels name="temperature_events" toName="ts">
      <Label value="Te_1_上升阶段" background="#FF6B6B"/>
      <Label value="Te_1_峰值时刻" background="#4ECDC4"/>
      <Label value="Te_1_下降阶段" background="#45B7D1"/>
      <Label value="Te_1_异常事件" background="#96CEB4"/>
      <Label value="Te_1_平台期" background="#FFEAA7"/>
    </TimeSeriesLabels>
  </TimeSeries>
</View>
```

## 数据格式要求

### 输入数据格式
- CSV文件，包含时间列和温度通道列
- 时间列名必须为 `time`
- 温度通道列名应包含 `Te`、`temp`、`Ti` 等关键词
- 支持多通道温度数据

### 示例数据
```csv
time,Te_1,Te_2,Te_3
0.0,100,150,200
0.001,120,170,220
0.002,140,190,240
...
```

## 部署到Kubernetes

```bash
kubectl apply -f temperature-annotation.yaml
```

## 自定义模型

可以通过修改 `temperature_predictor.py` 中的算法来自定义温度处理逻辑:

- 调整阈值检测算法
- 添加新的温度特征识别方法
- 自定义异常检测规则
- 优化梯度计算方法

## 测试

运行测试确保功能正常:

```bash
pytest test_temperature_backend.py -v
```

## API接口

### 健康检查
```
GET /health
```

### 模型信息
```
GET /model/info
```

### 预测接口
```
POST /predict
```

### 训练接口
```
POST /fit
```

## 故障排除

### 常见问题

1. **模型加载失败**: 检查依赖包安装和配置文件
2. **预测结果为空**: 确认输入数据格式和温度通道识别
3. **阈值设置不当**: 根据实际数据调整阈值参数
4. **内存不足**: 调整Docker容器的内存限制

### 日志查看

```bash
# Docker日志
docker logs temperature-annotation-ml-backend

# 查看模型日志
docker exec -it temperature-annotation-ml-backend tail -f /app/logs/model.log
```

## 性能优化

### 数据处理优化
- 使用并发加载多个炮号数据
- 支持数据预处理和缓存
- 优化异常值检测算法

### 预测性能优化
- 批量处理多个温度通道
- 并行计算不同特征检测
- 支持增量学习和模型更新
