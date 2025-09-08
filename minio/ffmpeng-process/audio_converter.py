#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台音频转换工具
支持Linux、macOS和Windows平台

功能说明：
1. 自动检测FFmpeg环境
2. 智能分析音频文件格式
3. 多策略转换方法
4. 音频质量验证
5. 批量处理支持

作者：AI助手
版本：3.0 (跨平台版本)
"""

import os
import sys
import subprocess
import platform
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import yaml

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audio_converter.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class FFmpegEnvironment:
    """FFmpeg环境检测和管理"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.is_available = False
        
    def detect_ffmpeg(self) -> bool:
        """检测FFmpeg是否可用"""
        try:
            # 尝试直接调用ffmpeg
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.ffmpeg_path = 'ffmpeg'
                self.is_available = True
                logger.info("✓ FFmpeg已安装并可用")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 尝试在常见路径中查找
        common_paths = self._get_common_paths()
        for path in common_paths:
            if os.path.exists(path):
                self.ffmpeg_path = path
                self.is_available = True
                logger.info(f"✓ 在 {path} 找到FFmpeg")
                return True
        
        logger.error("✗ 未找到FFmpeg")
        return False
    
    def detect_ffprobe(self) -> bool:
        """检测ffprobe是否可用"""
        try:
            result = subprocess.run(['ffprobe', '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.ffprobe_path = 'ffprobe'
                logger.info("✓ ffprobe已安装并可用")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 尝试在常见路径中查找
        common_paths = self._get_common_paths('ffprobe')
        for path in common_paths:
            if os.path.exists(path):
                self.ffprobe_path = path
                logger.info(f"✓ 在 {path} 找到ffprobe")
                return True
        
        logger.warning("⚠ ffprobe不可用，某些功能可能受限")
        return False
    
    def _get_common_paths(self, tool='ffmpeg') -> List[str]:
        """获取常见安装路径"""
        if self.system == 'linux':
            return [
                f'/usr/bin/{tool}',
                f'/usr/local/bin/{tool}',
                f'/opt/{tool}/bin/{tool}',
                f'/snap/bin/{tool}',
                f'/home/{os.getenv("USER", "user")}/.local/bin/{tool}'
            ]
        elif self.system == 'darwin':  # macOS
            return [
                f'/usr/local/bin/{tool}',
                f'/opt/homebrew/bin/{tool}',
                f'/usr/bin/{tool}',
                f'/Applications/{tool}.app/Contents/MacOS/{tool}'
            ]
        else:  # Windows
            return [
                f'C:\\ffmpeg\\bin\\{tool}.exe',
                f'C:\\Program Files\\ffmpeg\\bin\\{tool}.exe',
                f'C:\\Program Files (x86)\\ffmpeg\\bin\\{tool}.exe'
            ]
    
    def get_installation_guide(self) -> str:
        """获取安装指南"""
        if self.system == 'linux':
            return """
Linux安装FFmpeg:

Ubuntu/Debian:
  sudo apt update
  sudo apt install ffmpeg

CentOS/RHEL/Fedora:
  sudo dnf install ffmpeg
  # 或
  sudo yum install ffmpeg

Arch Linux:
  sudo pacman -S ffmpeg

Snap安装:
  sudo snap install ffmpeg
            """
        elif self.system == 'darwin':
            return """
macOS安装FFmpeg:

使用Homebrew (推荐):
  brew install ffmpeg

使用MacPorts:
  sudo port install ffmpeg

手动安装:
  1. 访问 https://ffmpeg.org/download.html
  2. 下载macOS版本
  3. 解压到 /usr/local/bin/
            """
        else:
            return """
Windows安装FFmpeg:

1. 访问 https://ffmpeg.org/download.html
2. 下载Windows版本
3. 解压到 C:\\ffmpeg\\
4. 将 C:\\ffmpeg\\bin 添加到PATH环境变量

或使用包管理器:
Chocolatey: choco install ffmpeg
Scoop: scoop install ffmpeg
            """

class AudioFileAnalyzer:
    """音频文件分析器"""
    
    def __init__(self, ffprobe_path: str):
        self.ffprobe_path = ffprobe_path
    
    def analyze_file(self, file_path: str) -> Dict:
        """分析音频文件"""
        logger.info(f"分析文件: {file_path}")
        
        try:
            # 基础信息分析
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-show_format',
                '-show_streams',
                '-print_format', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return self._parse_analysis(data)
            else:
                logger.warning(f"ffprobe分析失败: {result.stderr}")
                return self._fallback_analysis(file_path)
                
        except Exception as e:
            logger.error(f"文件分析失败: {e}")
            return self._fallback_analysis(file_path)
    
    def _parse_analysis(self, data: Dict) -> Dict:
        """解析分析结果"""
        analysis = {
            'format': data.get('format', {}),
            'streams': data.get('streams', []),
            'audio_streams': [],
            'video_streams': [],
            'has_audio': False,
            'has_video': False,
            'duration': 0,
            'file_size': 0
        }
        
        # 分析流信息
        for stream in analysis['streams']:
            if stream.get('codec_type') == 'audio':
                analysis['audio_streams'].append(stream)
                analysis['has_audio'] = True
            elif stream.get('codec_type') == 'video':
                analysis['video_streams'].append(stream)
                analysis['has_video'] = True
        
        # 获取时长和文件大小
        format_info = analysis['format']
        analysis['duration'] = float(format_info.get('duration', 0))
        analysis['file_size'] = int(format_info.get('size', 0))
        
        return analysis
    
    def _fallback_analysis(self, file_path: str) -> Dict:
        """备用分析方法"""
        try:
            file_size = os.path.getsize(file_path)
            return {
                'format': {},
                'streams': [],
                'audio_streams': [],
                'video_streams': [],
                'has_audio': True,  # 假设有音频
                'has_video': False,
                'duration': 0,
                'file_size': file_size
            }
        except Exception as e:
            logger.error(f"备用分析也失败: {e}")
            return {}

class AudioConverter:
    """音频转换器"""
    
    def __init__(self, ffmpeg_path: str, ffprobe_path: str, custom_params: Dict = None):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.analyzer = AudioFileAnalyzer(ffprobe_path)
        
        # 自定义参数配置
        self.custom_params = custom_params or {}
        
        # 转换方法列表
        self.conversion_methods = [
            self._method_standard,
            self._method_forced_mpeg,
            self._method_enhanced_probe,
            self._method_raw_pcm_s16le,
            self._method_raw_pcm_s16be,
            self._method_raw_pcm_f32le,
            self._method_custom
        ]
    
    def convert_file(self, input_file: str, output_file: str) -> bool:
        """转换音频文件"""
        logger.info(f"开始转换: {input_file} -> {output_file}")
        
        # 分析文件
        analysis = self.analyzer.analyze_file(input_file)
        
        # 创建输出目录
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 如果有自定义参数，优先尝试自定义方法
        if self.custom_params:
            logger.info("检测到自定义参数，优先使用自定义转换方法")
            try:
                success = self._method_custom(input_file, output_file, analysis)
                if success:
                    logger.info("✓ 自定义转换成功")
                    
                    # 验证输出文件
                    if self._verify_output(output_file):
                        return True
                    else:
                        logger.warning("自定义转换输出文件验证失败，尝试其他方法")
                else:
                    logger.warning("自定义转换失败，尝试其他方法")
            except Exception as e:
                logger.error(f"自定义转换出错: {e}")
        
        # 尝试各种转换方法
        for i, method in enumerate(self.conversion_methods, 1):
            # 跳过自定义方法，因为已经在上面尝试过了
            if method == self._method_custom:
                continue
                
            logger.info(f"尝试转换方法 {i}: {method.__name__}")
            
            try:
                success = method(input_file, output_file, analysis)
                if success:
                    logger.info(f"✓ 转换成功: {method.__name__}")
                    
                    # 验证输出文件
                    if self._verify_output(output_file):
                        return True
                    else:
                        logger.warning("输出文件验证失败，尝试下一种方法")
                        continue
                else:
                    logger.warning(f"转换方法 {method.__name__} 失败")
                    
            except Exception as e:
                logger.error(f"转换方法 {method.__name__} 出错: {e}")
                continue
        
        logger.error("所有转换方法都失败了")
        return False
    
    def _method_standard(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """标准转换方法"""
        cmd = [
            self.ffmpeg_path,
            '-i', input_file,
            '-vn',  # 禁用视频
            '-map', '0:a',  # 选择音频流
            '-c:a', 'pcm_s16le',  # 16位PCM编码
            '-y',  # 覆盖输出文件
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_forced_mpeg(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """强制MPEG格式转换"""
        cmd = [
            self.ffmpeg_path,
            '-f', 'mpeg',  # 强制MPEG格式
            '-i', input_file,
            '-vn',
            '-map', '0:a',
            '-c:a', 'pcm_s16le',
            '-y',
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_enhanced_probe(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """增强探测转换"""
        cmd = [
            self.ffmpeg_path,
            '-probesize', '10M',
            '-analyzeduration', '10M',
            '-i', input_file,
            '-vn',
            '-map', '0:a',
            '-c:a', 'pcm_s16le',
            '-y',
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_raw_pcm_s16le(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """原始PCM 16位小端序转换"""
        cmd = [
            self.ffmpeg_path,
            '-f', 's16le',  # 16位小端序PCM
            '-ar', '44100',  # 44.1kHz采样率
            '-ac', '1',  # 单声道
            '-i', input_file,
            '-c:a', 'pcm_s16le',
            '-y',
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_raw_pcm_s16be(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """原始PCM 16位大端序转换"""
        cmd = [
            self.ffmpeg_path,
            '-f', 's16be',  # 16位大端序PCM
            '-ar', '44100',
            '-ac', '1',
            '-i', input_file,
            '-c:a', 'pcm_s16le',
            '-y',
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_raw_pcm_f32le(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """原始PCM 32位浮点转换"""
        cmd = [
            self.ffmpeg_path,
            '-f', 'f32le',  # 32位浮点小端序
            '-ar', '44100',
            '-ac', '1',
            '-i', input_file,
            '-c:a', 'pcm_s16le',
            '-y',
            output_file
        ]
        return self._execute_conversion(cmd)
    
    def _method_custom(self, input_file: str, output_file: str, analysis: Dict) -> bool:
        """自定义参数转换"""
        if not self.custom_params:
            return False
            
        logger.info("使用自定义参数进行转换")
        
        # 构建基础命令
        cmd = [self.ffmpeg_path]
        
        # 对于原始PCM数据，需要指定输入格式
        # 如果没有指定输入格式，尝试自动检测
        if 'input_format' not in self.custom_params:
            # 尝试常见的PCM格式
            pcm_formats = ['s16le', 's16be', 'f32le', 'f32be', 's24le', 's24be']
            for fmt in pcm_formats:
                test_cmd = [self.ffmpeg_path, '-f', fmt, '-ar', '44100', '-ac', '1', '-i', input_file, '-t', '1', '-f', 'null', '-']
                try:
                    result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.custom_params['input_format'] = fmt
                        logger.info(f"自动检测到输入格式: {fmt}")
                        break
                except:
                    continue
        
        # 添加输入参数
        if 'input_format' in self.custom_params:
            cmd.extend(['-f', self.custom_params['input_format']])
        
        if 'input_sample_rate' in self.custom_params:
            cmd.extend(['-ar', str(self.custom_params['input_sample_rate'])])
            
        if 'input_channels' in self.custom_params:
            cmd.extend(['-ac', str(self.custom_params['input_channels'])])
        
        # 添加探测参数
        if 'probesize' in self.custom_params:
            cmd.extend(['-probesize', str(self.custom_params['probesize'])])
            
        if 'analyzeduration' in self.custom_params:
            cmd.extend(['-analyzeduration', str(self.custom_params['analyzeduration'])])
        
        # 添加输入文件
        cmd.extend(['-i', input_file])
        
        # 添加输出参数
        if 'disable_video' in self.custom_params and self.custom_params['disable_video']:
            cmd.append('-vn')
            
        # 只有在有音频流时才映射音频
        if 'map_audio' in self.custom_params and self.custom_params['map_audio']:
            # 对于原始PCM数据，不需要映射音频流
            if 'input_format' not in self.custom_params:
                cmd.extend(['-map', '0:a'])
        
        # 音频编码参数
        if 'audio_codec' in self.custom_params:
            cmd.extend(['-c:a', self.custom_params['audio_codec']])
        
        if 'output_sample_rate' in self.custom_params:
            cmd.extend(['-ar', str(self.custom_params['output_sample_rate'])])
            
        if 'output_channels' in self.custom_params:
            cmd.extend(['-ac', str(self.custom_params['output_channels'])])
            
        if 'audio_bitrate' in self.custom_params:
            cmd.extend(['-b:a', str(self.custom_params['audio_bitrate'])])
            
        if 'audio_quality' in self.custom_params:
            cmd.extend(['-q:a', str(self.custom_params['audio_quality'])])
        
        # 添加其他自定义参数
        if 'extra_params' in self.custom_params:
            if isinstance(self.custom_params['extra_params'], list):
                cmd.extend(self.custom_params['extra_params'])
            elif isinstance(self.custom_params['extra_params'], str):
                cmd.extend(self.custom_params['extra_params'].split())
        
        # 添加输出文件
        cmd.extend(['-y', output_file])
        
        logger.info(f"自定义转换命令: {' '.join(cmd)}")
        return self._execute_conversion(cmd)
    
    def _execute_conversion(self, cmd: List[str]) -> bool:
        """执行转换命令"""
        try:
            logger.debug(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                return True
            else:
                logger.debug(f"命令失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("转换超时")
            return False
        except Exception as e:
            logger.error(f"执行转换时出错: {e}")
            return False
    
    def _verify_output(self, output_file: str) -> bool:
        """验证输出文件"""
        try:
            if not os.path.exists(output_file):
                return False
            
            file_size = os.path.getsize(output_file)
            if file_size == 0:
                return False
            
            # 使用ffprobe验证文件格式
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-show_format',
                '-show_streams',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"验证输出文件时出错: {e}")
            return False

class AudioValidator:
    """音频数据验证器"""
    
    def __init__(self, python_cmd="python3"):
        self.python_cmd = python_cmd
        
    def validate_data_file(self, data_file: str, meta_file: str) -> bool:
        """验证数据文件完整性"""
        logger.info(f"开始验证数据文件: {data_file}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(data_file):
                logger.error(f"数据文件不存在: {data_file}")
                return False
                
            if not os.path.exists(meta_file):
                logger.error(f"元数据文件不存在: {meta_file}")
                return False
            
            # 运行基础验证
            logger.info("运行基础验证...")
            result = subprocess.run([
                self.python_cmd, "audio_data_validator.py", data_file, meta_file
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info("✓ 基础验证通过")
                
                # 运行高级验证
                logger.info("运行高级验证...")
                result = subprocess.run([
                    self.python_cmd, "advanced_audio_validator.py", data_file, meta_file
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info("✓ 高级验证通过")
                    return True
                else:
                    logger.warning("高级验证失败，但基础验证通过")
                    return True  # 基础验证通过即可
            else:
                logger.error("✗ 数据验证失败")
                logger.error(f"验证错误: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("验证超时")
            return False
        except Exception as e:
            logger.error(f"验证过程出错: {e}")
            return False

class AudioConverterApp:
    """音频转换应用程序主类"""
    
    def __init__(self, custom_params: Dict = None):
        self.env = FFmpegEnvironment()
        self.converter = None
        self.validator = AudioValidator()
        self.custom_params = custom_params or {}
        
    def initialize(self) -> bool:
        """初始化应用程序"""
        logger.info("初始化音频转换工具...")
        
        # 检测FFmpeg环境
        if not self.env.detect_ffmpeg():
            logger.error("FFmpeg未安装或不可用")
            print("\n" + "="*60)
            print("FFmpeg安装指南:")
            print(self.env.get_installation_guide())
            print("="*60)
            return False
        
        # 检测ffprobe
        self.env.detect_ffprobe()
        
        # 初始化转换器
        self.converter = AudioConverter(self.env.ffmpeg_path, self.env.ffprobe_path, self.custom_params)
        
        logger.info("✓ 音频转换工具初始化完成")
        return True
    
    def convert_single_file(self, input_file: str, output_file: Optional[str] = None, 
                          skip_validation: bool = False) -> bool:
        """转换单个文件"""
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return False
        
        if output_file is None:
            # 自动生成输出文件名
            input_path = Path(input_file)
            output_file = str(input_path.parent / "output" / f"{input_path.stem}_audio.wav")
        
        # 检查是否有对应的.meta文件
        meta_file = f"{input_file}.meta"
        
        if not skip_validation and os.path.exists(meta_file):
            logger.info(f"发现元数据文件: {meta_file}")
            logger.info("在转换前进行数据完整性验证...")
            
            if not self.validator.validate_data_file(input_file, meta_file):
                logger.error("数据验证失败，跳过转换")
                return False
            
            logger.info("✓ 数据验证通过，开始转换")
        elif not skip_validation:
            logger.warning(f"未找到元数据文件: {meta_file}")
            logger.warning("将跳过数据验证，直接进行转换")
        
        return self.converter.convert_file(input_file, output_file)
    
    def convert_batch(self, input_dir: str, output_dir: str = "output", 
                     file_patterns: List[str] = None, skip_validation: bool = False) -> Dict:
        """批量转换文件"""
        if file_patterns is None:
            file_patterns = ['*_data', '*.dat', '*.bin']
        
        logger.info(f"开始批量转换: {input_dir} -> {output_dir}")
        
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'validation_failed': 0,
            'files': []
        }
        
        # 查找输入文件
        input_path = Path(input_dir)
        input_files = []
        
        for pattern in file_patterns:
            input_files.extend(input_path.glob(pattern))
        
        results['total'] = len(input_files)
        
        # 转换每个文件
        for input_file in input_files:
            output_file = str(Path(output_dir) / f"{input_file.stem}_audio.wav")
            meta_file = f"{input_file}.meta"
            
            logger.info(f"处理文件: {input_file.name}")
            
            # 检查是否有对应的.meta文件并进行验证
            validation_passed = True
            if not skip_validation and os.path.exists(meta_file):
                logger.info(f"发现元数据文件: {meta_file}")
                logger.info("进行数据完整性验证...")
                
                if not self.validator.validate_data_file(str(input_file), meta_file):
                    logger.error(f"✗ 数据验证失败: {input_file.name}")
                    results['validation_failed'] += 1
                    validation_passed = False
                else:
                    logger.info(f"✓ 数据验证通过: {input_file.name}")
            elif not skip_validation:
                logger.warning(f"未找到元数据文件: {meta_file}")
                logger.warning("将跳过数据验证，直接进行转换")
            
            # 如果验证通过，进行转换
            if validation_passed:
                success = self.converter.convert_file(str(input_file), output_file)
                
                file_result = {
                    'input': str(input_file),
                    'output': output_file,
                    'success': success,
                    'validation_passed': True
                }
                
                if success:
                    results['success'] += 1
                    logger.info(f"✓ 转换成功: {input_file.name}")
                else:
                    results['failed'] += 1
                    logger.error(f"✗ 转换失败: {input_file.name}")
            else:
                file_result = {
                    'input': str(input_file),
                    'output': output_file,
                    'success': False,
                    'validation_passed': False
                }
                results['failed'] += 1
            
            results['files'].append(file_result)
        
        return results

def load_config_file(config_path: str) -> Dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"加载配置文件: {config_path}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}

def parse_custom_params(args: List[str]) -> Dict:
    """解析自定义参数"""
    custom_params = {}
    config_file = None
    config_profile = None
    
    # 查找配置文件参数
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--config':
            if i + 1 < len(args):
                config_file = args[i + 1]
                i += 2
            else:
                logger.warning("缺少配置文件路径")
                i += 1
        elif arg == '--profile':
            if i + 1 < len(args):
                config_profile = args[i + 1]
                i += 2
            else:
                logger.warning("缺少配置文件名")
                i += 1
        else:
            i += 1
    
    # 加载配置文件
    if config_file:
        config = load_config_file(config_file)
        if config_profile and config_profile in config:
            custom_params.update(config[config_profile])
            logger.info(f"使用配置: {config_profile}")
        elif 'default' in config:
            custom_params.update(config['default'])
            logger.info("使用默认配置")
    elif os.path.exists('audio_config.yaml'):
        # 尝试加载默认配置文件
        config = load_config_file('audio_config.yaml')
        if config_profile and config_profile in config:
            custom_params.update(config[config_profile])
            logger.info(f"使用默认配置文件中的配置: {config_profile}")
        elif 'default' in config:
            custom_params.update(config['default'])
            logger.info("使用默认配置文件中的默认配置")
    
    # 查找命令行自定义参数
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg.startswith('--custom-'):
            param_name = arg[9:]  # 移除 '--custom-' 前缀
            
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                param_value = args[i + 1]
                
                # 处理不同类型的参数
                if param_name in ['probesize', 'analyzeduration', 'input_sample_rate', 
                                'input_channels', 'output_sample_rate', 'output_channels', 
                                'audio_bitrate', 'audio_quality']:
                    try:
                        custom_params[param_name] = int(param_value)
                    except ValueError:
                        logger.warning(f"无效的数值参数: {param_name}={param_value}")
                elif param_name in ['disable_video', 'map_audio']:
                    custom_params[param_name] = param_value.lower() in ['true', '1', 'yes']
                else:
                    custom_params[param_name] = param_value
                
                i += 2  # 跳过参数值
            else:
                logger.warning(f"缺少参数值: {arg}")
                i += 1
        else:
            i += 1
    
    return custom_params

def main():
    """主函数"""
    print("=" * 60)
    print("跨平台音频转换工具")
    print("支持 Linux, macOS, Windows")
    print("=" * 60)
    
    # 解析自定义参数
    custom_params = parse_custom_params(sys.argv)
    
    # 创建应用程序实例
    app = AudioConverterApp(custom_params)
    
    # 初始化
    if not app.initialize():
        sys.exit(1)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  单文件转换: python audio_converter.py <输入文件> [输出文件] [选项]")
        print("  批量转换:   python audio_converter.py --batch <输入目录> [输出目录] [选项]")
        print("\n选项:")
        print("  --skip-validation                   跳过数据完整性验证")
        print("  --config <配置文件>                  指定配置文件")
        print("  --profile <配置名>                   指定配置名称")
        print("  --custom-<参数名> <值>              自定义FFmpeg参数")
        print("\n配置文件支持:")
        print("  --config audio_config.yaml         使用指定配置文件")
        print("  --profile high_quality             使用高质量配置")
        print("  --profile professional              使用专业配置")
        print("  --profile compressed                使用压缩配置")
        print("\n自定义参数示例:")
        print("  --custom-audio_codec pcm_s24le      音频编码器")
        print("  --custom-output_sample_rate 48000  输出采样率")
        print("  --custom-output_channels 2         输出声道数")
        print("  --custom-audio_bitrate 192k        音频比特率")
        print("  --custom-input_format s16le        输入格式")
        print("  --custom-probesize 20M             探测大小")
        print("  --custom-disable_video true        禁用视频")
        print("  --custom-map_audio true            映射音频流")
        print("  --custom-extra_params '-threads 4' 额外参数")
        print("\n示例:")
        print("  python audio_converter.py S-ZTCJ03DZ0043-8_data")
        print("  python audio_converter.py --batch ./input_files")
        print("  python audio_converter.py S-ZTCJ03DZ0043-8_data --skip-validation")
        print("  python audio_converter.py S-ZTCJ03DZ0043-8_data --profile high_quality")
        print("  python audio_converter.py S-ZTCJ03DZ0043-8_data --custom-audio_codec pcm_s24le --custom-output_sample_rate 48000")
        sys.exit(1)
    
    # 解析参数
    skip_validation = '--skip-validation' in sys.argv
    
    # 处理批量转换
    if sys.argv[1] == '--batch':
        if len(sys.argv) < 3:
            print("错误: 批量转换需要指定输入目录")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != '--skip-validation' else "output"
        
        results = app.convert_batch(input_dir, output_dir, skip_validation=skip_validation)
        
        print(f"\n批量转换完成:")
        print(f"  总文件数: {results['total']}")
        print(f"  成功: {results['success']}")
        print(f"  失败: {results['failed']}")
        if 'validation_failed' in results:
            print(f"  验证失败: {results['validation_failed']}")
        
        if results['failed'] > 0:
            print("\n失败的文件:")
            for file_result in results['files']:
                if not file_result['success']:
                    reason = "验证失败" if not file_result.get('validation_passed', True) else "转换失败"
                    print(f"  - {file_result['input']} ({reason})")
    
    else:
        # 单文件转换
        input_file = sys.argv[1]
        output_file = None
        
        # 查找输出文件参数（排除所有配置参数）
        for i, arg in enumerate(sys.argv[2:], 2):
            if (arg != '--skip-validation' and 
                not arg.startswith('--custom-') and 
                arg != '--config' and 
                arg != '--profile' and
                not (i > 2 and sys.argv[i-1] in ['--config', '--profile']) and
                not (i > 2 and sys.argv[i-1].startswith('--custom-'))):
                output_file = arg
                break
        
        success = app.convert_single_file(input_file, output_file, skip_validation=skip_validation)
        
        if success:
            print(f"\n✓ 转换成功!")
            if output_file:
                print(f"输出文件: {output_file}")
        else:
            print(f"\n✗ 转换失败!")
            sys.exit(1)

if __name__ == "__main__":
    main()
