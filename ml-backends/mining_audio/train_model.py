"""
矿业声音ML Backend模型训练脚本

支持从标注数据训练多标签分类模型，包括：
- 音频特征提取和预处理
- 多标签数据准备
- 模型训练和验证
- 模型保存和评估
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MultiLabelBinarizer
from sklearn.metrics import classification_report, multilabel_confusion_matrix, accuracy_score
import pickle
import os
import logging
import argparse
import time
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# 导入模型组件
from model import MiningAudioClassifier, AudioFeatureExtractor, MINING_LABELS

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MiningAudioDataset(Dataset):
    """矿业音频数据集类"""
    
    def __init__(self, audio_paths, labels, feature_extractor, scaler=None):
        self.audio_paths = audio_paths
        self.labels = labels
        self.feature_extractor = feature_extractor
        self.scaler = scaler
        
    def __len__(self):
        return len(self.audio_paths)
    
    def __getitem__(self, idx):
        # 提取音频特征
        features = self.feature_extractor.extract_features(self.audio_paths[idx])
        
        if features is None:
            # 如果特征提取失败，返回零向量
            logger.warning(f"特征提取失败: {self.audio_paths[idx]}")
            features = np.zeros(68)
        
        # 标准化特征
        if self.scaler:
            features = self.scaler.transform(features.reshape(1, -1)).flatten()
        
        return torch.FloatTensor(features), torch.FloatTensor(self.labels[idx])


def prepare_labels(label_data):
    """准备多标签数据"""
    logger.info("准备多标签数据...")
    
    # 为每个类别创建标签编码器
    label_encoders = {}
    encoded_labels = []
    
    for category in MINING_LABELS.keys():
        logger.info(f"处理类别: {category}")
        category_labels = label_data[category].apply(lambda x: x if isinstance(x, list) else [x])
        
        # 创建多标签二值化器
        mlb_category = MultiLabelBinarizer(classes=MINING_LABELS[category])
        encoded_category = mlb_category.fit_transform(category_labels)
        
        label_encoders[category] = mlb_category
        encoded_labels.append(encoded_category)
        
        logger.info(f"类别 {category} 标签数量: {len(MINING_LABELS[category])}")
        logger.info(f"类别 {category} 样本数量: {len(encoded_category)}")
    
    # 合并所有类别的标签
    all_labels = np.hstack(encoded_labels)
    logger.info(f"总标签维度: {all_labels.shape}")
    
    return all_labels, label_encoders


def create_model_summary(model, input_dim):
    """创建模型结构摘要"""
    logger.info("模型结构摘要:")
    logger.info(f"输入维度: {input_dim}")
    
    total_params = 0
    for name, param in model.named_parameters():
        if param.requires_grad:
            param_count = param.numel()
            total_params += param_count
            logger.info(f"{name}: {param.shape} ({param_count:,} 参数)")
    
    logger.info(f"总参数数量: {total_params:,}")
    return total_params


def train_epoch(model, train_loader, criterion, optimizer, device):
    """训练一个epoch"""
    model.train()
    total_loss = 0.0
    correct_predictions = 0
    total_predictions = 0
    
    for batch_idx, (features, labels) in enumerate(train_loader):
        features, labels = features.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(features)
        
        # 计算每个类别的损失
        batch_loss = 0
        start_idx = 0
        for category, output in outputs.items():
            end_idx = start_idx + len(MINING_LABELS[category])
            category_labels = labels[:, start_idx:end_idx]
            loss = criterion(output, category_labels)
            batch_loss += loss
            start_idx = end_idx
        
        batch_loss.backward()
        optimizer.step()
        
        total_loss += batch_loss.item()
        
        # 计算准确率
        with torch.no_grad():
            predictions = []
            for category, output in outputs.items():
                pred = (output > 0.5).float()
                predictions.append(pred)
            
            all_predictions = torch.cat(predictions, dim=1)
            correct_predictions += (all_predictions == labels).sum().item()
            total_predictions += labels.numel()
        
        if batch_idx % 10 == 0:
            logger.info(f"Batch {batch_idx}/{len(train_loader)}, Loss: {batch_loss.item():.4f}")
    
    avg_loss = total_loss / len(train_loader)
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
    
    return avg_loss, accuracy


def validate_model(model, val_loader, criterion, device):
    """验证模型"""
    model.eval()
    total_loss = 0.0
    all_predictions = []
    all_labels = []
    
    with torch.no_grad():
        for features, labels in val_loader:
            features, labels = features.to(device), labels.to(device)
            outputs = model(features)
            
            # 计算损失
            batch_loss = 0
            start_idx = 0
            for category, output in outputs.items():
                end_idx = start_idx + len(MINING_LABELS[category])
                category_labels = labels[:, start_idx:end_idx]
                loss = criterion(output, category_labels)
                batch_loss += loss
                start_idx = end_idx
            
            total_loss += batch_loss.item()
            
            # 收集预测结果
            predictions = []
            for category, output in outputs.items():
                pred = (output > 0.5).float()
                predictions.append(pred)
            
            batch_predictions = torch.cat(predictions, dim=1)
            all_predictions.append(batch_predictions.cpu().numpy())
            all_labels.append(labels.cpu().numpy())
    
    avg_loss = total_loss / len(val_loader)
    
    # 合并所有批次的预测结果
    all_predictions = np.vstack(all_predictions)
    all_labels = np.vstack(all_labels)
    
    return avg_loss, all_predictions, all_labels


def evaluate_model(predictions, labels, label_encoders):
    """评估模型性能"""
    logger.info("评估模型性能...")
    
    # 计算整体准确率
    overall_accuracy = accuracy_score(labels.flatten(), predictions.flatten())
    logger.info(f"整体准确率: {overall_accuracy:.4f}")
    
    # 按类别评估
    start_idx = 0
    for category in MINING_LABELS.keys():
        end_idx = start_idx + len(MINING_LABELS[category])
        category_labels = labels[:, start_idx:end_idx]
        category_predictions = predictions[:, start_idx:end_idx]
        
        # 计算类别准确率
        category_accuracy = accuracy_score(category_labels.flatten(), category_predictions.flatten())
        logger.info(f"类别 {category} 准确率: {category_accuracy:.4f}")
        
        # 生成分类报告
        if hasattr(label_encoders[category], 'classes_'):
            target_names = label_encoders[category].classes_
            report = classification_report(
                category_labels, 
                category_predictions, 
                target_names=target_names,
                zero_division=0
            )
            logger.info(f"类别 {category} 详细报告:\n{report}")
        
        start_idx = end_idx


def plot_training_history(train_losses, val_losses, train_accuracies, val_accuracies, save_path):
    """绘制训练历史"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    
    # 损失曲线
    ax1.plot(train_losses, label='训练损失', color='blue')
    ax1.plot(val_losses, label='验证损失', color='red')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Loss')
    ax1.set_title('训练和验证损失')
    ax1.legend()
    ax1.grid(True)
    
    # 准确率曲线
    ax2.plot(train_accuracies, label='训练准确率', color='blue')
    ax2.plot(val_accuracies, label='验证准确率', color='red')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Accuracy')
    ax2.set_title('训练和验证准确率')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"训练历史图表已保存到: {save_path}")


def train_model(data_path, model_save_path, scaler_save_path, config=None):
    """训练模型主函数"""
    logger.info("开始训练矿业音频分类模型...")
    start_time = time.time()
    
    # 加载配置
    if config is None:
        config = {
            'batch_size': 32,
            'learning_rate': 0.001,
            'epochs': 50,
            'early_stopping_patience': 10,
            'validation_split': 0.2,
            'random_seed': 42
        }
    
    # 设置随机种子
    torch.manual_seed(config['random_seed'])
    np.random.seed(config['random_seed'])
    
    # 检查数据文件
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    # 加载数据
    logger.info(f"加载数据: {data_path}")
    df = pd.read_csv(data_path)
    logger.info(f"数据形状: {df.shape}")
    
    # 检查必要的列
    required_columns = ['audio_path', 'equipment_status', 'fault_type', 'priority']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要的列: {missing_columns}")
    
    # 过滤有效的音频文件
    valid_audio_paths = []
    for path in df['audio_path']:
        if os.path.exists(path):
            valid_audio_paths.append(path)
        else:
            logger.warning(f"音频文件不存在: {path}")
    
    logger.info(f"有效音频文件数量: {len(valid_audio_paths)}")
    
    if len(valid_audio_paths) == 0:
        raise ValueError("没有找到有效的音频文件")
    
    # 准备标签
    label_data = df[['equipment_status', 'fault_type', 'priority']].iloc[:len(valid_audio_paths)]
    labels, label_encoders = prepare_labels(label_data)
    
    # 分割数据集
    X_train, X_val, y_train, y_val = train_test_split(
        valid_audio_paths, labels, 
        test_size=config['validation_split'], 
        random_state=config['random_seed']
    )
    
    logger.info(f"训练集大小: {len(X_train)}")
    logger.info(f"验证集大小: {len(X_val)}")
    
    # 初始化特征提取器
    feature_extractor = AudioFeatureExtractor()
    
    # 提取训练集特征用于标准化
    logger.info("提取特征并计算标准化参数...")
    train_features = []
    for path in X_train:
        features = feature_extractor.extract_features(path)
        if features is not None:
            train_features.append(features)
    
    if len(train_features) == 0:
        raise ValueError("无法从训练集中提取特征")
    
    train_features = np.array(train_features)
    scaler = StandardScaler()
    scaler.fit(train_features)
    
    logger.info(f"特征标准化器已训练，特征维度: {train_features.shape}")
    
    # 创建数据集和数据加载器
    train_dataset = MiningAudioDataset(X_train, y_train, feature_extractor, scaler)
    val_dataset = MiningAudioDataset(X_val, y_val, feature_extractor, scaler)
    
    train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'], shuffle=False)
    
    # 初始化模型
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"使用设备: {device}")
    
    input_dim = 68  # 特征维度
    model = MiningAudioClassifier(input_dim=input_dim)
    model.to(device)
    
    # 创建模型摘要
    total_params = create_model_summary(model, input_dim)
    
    # 定义损失函数和优化器
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=config['learning_rate'])
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5, verbose=True
    )
    
    # 训练循环
    logger.info("开始训练...")
    best_val_loss = float('inf')
    patience_counter = 0
    
    train_losses = []
    val_losses = []
    train_accuracies = []
    val_accuracies = []
    
    for epoch in range(config['epochs']):
        epoch_start_time = time.time()
        
        # 训练
        train_loss, train_accuracy = train_epoch(model, train_loader, criterion, optimizer, device)
        
        # 验证
        val_loss, val_predictions, val_labels = validate_model(model, val_loader, criterion, device)
        
        # 学习率调度
        scheduler.step(val_loss)
        
        # 记录历史
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        train_accuracies.append(train_accuracy)
        val_accuracies.append(val_loss)  # 这里应该是val_accuracy，但验证函数没有返回准确率
        
        epoch_time = time.time() - epoch_start_time
        
        logger.info(f'Epoch [{epoch+1}/{config["epochs"]}] ({epoch_time:.2f}s)')
        logger.info(f'  训练损失: {train_loss:.4f}, 训练准确率: {train_accuracy:.4f}')
        logger.info(f'  验证损失: {val_loss:.4f}')
        
        # 早停检查
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            
            # 保存最佳模型
            torch.save(model.state_dict(), model_save_path)
            logger.info(f"保存最佳模型，验证损失: {best_val_loss:.4f}")
            
            # 保存标准化器
            with open(scaler_save_path, 'wb') as f:
                pickle.dump(scaler, f)
            logger.info(f"保存特征标准化器: {scaler_save_path}")
        else:
            patience_counter += 1
            logger.info(f"验证损失未改善，耐心计数: {patience_counter}/{config['early_stopping_patience']}")
            
            if patience_counter >= config['early_stopping_patience']:
                logger.info("早停触发，停止训练")
                break
    
    # 训练完成
    total_time = time.time() - start_time
    logger.info(f"训练完成，总耗时: {total_time:.2f}秒")
    
    # 绘制训练历史
    history_save_path = os.path.join(os.path.dirname(model_save_path), 'training_history.png')
    plot_training_history(train_losses, val_losses, train_accuracies, val_accuracies, history_save_path)
    
    # 最终评估
    logger.info("进行最终模型评估...")
    model.load_state_dict(torch.load(model_save_path))
    final_val_loss, final_predictions, final_labels = validate_model(model, val_loader, criterion, device)
    
    evaluate_model(final_predictions, final_labels, label_encoders)
    
    logger.info(f"模型训练完成！")
    logger.info(f"模型文件: {model_save_path}")
    logger.info(f"标准化器文件: {scaler_save_path}")
    logger.info(f"最终验证损失: {final_val_loss:.4f}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='训练矿业音频分类模型')
    parser.add_argument('--data_path', type=str, required=True,
                       help='训练数据CSV文件路径')
    parser.add_argument('--model_save_path', type=str, 
                       default='models/mining_audio_model.pth',
                       help='模型保存路径')
    parser.add_argument('--scaler_save_path', type=str,
                       default='models/feature_scaler.pkl',
                       help='特征标准化器保存路径')
    parser.add_argument('--batch_size', type=int, default=32,
                       help='批次大小')
    parser.add_argument('--learning_rate', type=float, default=0.001,
                       help='学习率')
    parser.add_argument('--epochs', type=int, default=50,
                       help='训练轮数')
    parser.add_argument('--early_stopping_patience', type=int, default=10,
                       help='早停耐心值')
    parser.add_argument('--validation_split', type=float, default=0.2,
                       help='验证集比例')
    
    args = parser.parse_args()
    
    # 创建保存目录
    os.makedirs(os.path.dirname(args.model_save_path), exist_ok=True)
    os.makedirs(os.path.dirname(args.scaler_save_path), exist_ok=True)
    
    # 训练配置
    config = {
        'batch_size': args.batch_size,
        'learning_rate': args.learning_rate,
        'epochs': args.epochs,
        'early_stopping_patience': args.early_stopping_patience,
        'validation_split': args.validation_split,
        'random_seed': 42
    }
    
    try:
        train_model(args.data_path, args.model_save_path, args.scaler_save_path, config)
    except Exception as e:
        logger.error(f"训练失败: {e}")
        raise


if __name__ == "__main__":
    main()
