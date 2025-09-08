#!/bin/bash
# 音频文件转换脚本 (Linux/macOS版本)
# 将dat文件转换为WAV格式
# 作者: AI助手
# 日期: 2025年9月8日

# 设置脚本选项
set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示标题
show_header() {
    echo "========================================"
    echo "音频文件转换工具 (Linux/macOS版本)"
    echo "========================================"
    echo
}

# 检查FFmpeg是否安装
check_ffmpeg() {
    log_info "检查FFmpeg环境..."
    
    if command -v ffmpeg >/dev/null 2>&1; then
        FFMPEG_CMD="ffmpeg"
        log_success "FFmpeg已安装"
        log_info "版本信息: $(ffmpeg -version | head -n 1)"
    else
        log_error "FFmpeg未安装"
        show_installation_guide
        exit 1
    fi
    
    if command -v ffprobe >/dev/null 2>&1; then
        FFPROBE_CMD="ffprobe"
        log_success "ffprobe工具可用"
    else
        log_warning "ffprobe工具不可用，某些功能可能受限"
        FFPROBE_CMD=""
    fi
    
    echo
}

# 显示安装指南
show_installation_guide() {
    echo
    echo "========================================"
    echo "FFmpeg安装指南"
    echo "========================================"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Linux安装方法:"
        echo "  Ubuntu/Debian:"
        echo "    sudo apt update && sudo apt install ffmpeg"
        echo "  CentOS/RHEL/Fedora:"
        echo "    sudo dnf install ffmpeg"
        echo "  Arch Linux:"
        echo "    sudo pacman -S ffmpeg"
        echo "  Snap安装:"
        echo "    sudo snap install ffmpeg"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS安装方法:"
        echo "  使用Homebrew (推荐):"
        echo "    brew install ffmpeg"
        echo "  使用MacPorts:"
        echo "    sudo port install ffmpeg"
        echo "  手动安装:"
        echo "    1. 访问 https://ffmpeg.org/download.html"
        echo "    2. 下载macOS版本"
        echo "    3. 解压到 /usr/local/bin/"
    else
        echo "请访问 https://ffmpeg.org/download.html 下载对应版本"
    fi
    
    echo "========================================"
    echo
}

# 分析文件结构
analyze_file() {
    local input_file="$1"
    
    log_info "分析文件结构: $input_file"
    
    if [[ -n "$FFPROBE_CMD" ]]; then
        echo "文件流信息:"
        if $FFPROBE_CMD -v quiet -show_streams -i "$input_file" 2>/dev/null; then
            echo
        else
            log_warning "无法获取流信息，可能文件格式不支持"
        fi
    else
        log_warning "ffprobe不可用，跳过文件分析"
    fi
    
    echo
}

# 执行转换
convert_audio() {
    local input_file="$1"
    local output_file="$2"
    local method="$3"
    
    log_info "开始转换音频文件..."
    log_info "输入: $input_file"
    log_info "输出: $output_file"
    log_info "方法: $method"
    echo
    
    case "$method" in
        "standard")
            log_info "使用标准转换方法..."
            $FFMPEG_CMD -probesize 10M -analyzeduration 10M \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "forced")
            log_info "使用强制格式转换方法..."
            $FFMPEG_CMD -f mpeg \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "enhanced")
            log_info "使用增强探测转换方法..."
            $FFMPEG_CMD -probesize 20M -analyzeduration 20M \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_s16le")
            log_info "使用原始PCM 16位小端序转换..."
            $FFMPEG_CMD -f s16le -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_s16be")
            log_info "使用原始PCM 16位大端序转换..."
            $FFMPEG_CMD -f s16be -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_f32le")
            log_info "使用原始PCM 32位浮点转换..."
            $FFMPEG_CMD -f f32le -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        *)
            log_error "未知的转换方法: $method"
            return 1
            ;;
    esac
    
    return $?
}

# 验证输出文件
verify_output() {
    local output_file="$1"
    
    if [[ -f "$output_file" ]]; then
        local file_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
        log_success "输出文件创建成功"
        log_info "文件路径: $output_file"
        log_info "文件大小: $(( file_size / 1024 )) KB"
        
        if [[ -n "$FFPROBE_CMD" ]]; then
            echo
            log_info "输出文件详细信息:"
            if $FFPROBE_CMD -v quiet -show_format -show_streams "$output_file" 2>/dev/null; then
                echo
            else
                log_warning "无法获取输出文件详细信息"
            fi
        fi
        
        return 0
    else
        log_error "输出文件创建失败"
        return 1
    fi
}

# 批量转换
batch_convert() {
    local input_dir="$1"
    local output_dir="${2:-output}"
    
    log_info "开始批量转换..."
    log_info "输入目录: $input_dir"
    log_info "输出目录: $output_dir"
    echo
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    # 查找输入文件
    local files=()
    while IFS= read -r -d '' file; do
        files+=("$file")
    done < <(find "$input_dir" -maxdepth 1 -type f \( -name "*_data" -o -name "*.dat" -o -name "*.bin" \) -print0)
    
    if [[ ${#files[@]} -eq 0 ]]; then
        log_warning "未找到可转换的文件"
        return 0
    fi
    
    log_info "找到 ${#files[@]} 个文件需要转换"
    echo
    
    local success_count=0
    local total_count=${#files[@]}
    
    # 转换每个文件
    for input_file in "${files[@]}"; do
        local filename=$(basename "$input_file")
        local output_file="$output_dir/${filename%.*}_audio.wav"
        
        log_info "转换文件: $filename"
        
        # 尝试不同的转换方法
        local conversion_methods=("standard" "forced" "enhanced" "raw_s16le" "raw_s16be" "raw_f32le")
        local converted=false
        
        for method in "${conversion_methods[@]}"; do
            if convert_audio "$input_file" "$output_file" "$method"; then
                if verify_output "$output_file"; then
                    log_success "转换成功: $filename (方法: $method)"
                    ((success_count++))
                    converted=true
                    break
                else
                    log_warning "方法 $method 转换失败，尝试下一种方法"
                fi
            else
                log_warning "方法 $method 转换失败，尝试下一种方法"
            fi
        done
        
        if [[ "$converted" == false ]]; then
            log_error "所有转换方法都失败: $filename"
        fi
        
        echo
    done
    
    # 显示结果
    echo "========================================"
    log_info "批量转换完成"
    echo "  总文件数: $total_count"
    echo "  成功: $success_count"
    echo "  失败: $((total_count - success_count))"
    echo "========================================"
}

# 主程序
main() {
    show_header
    
    # 检查FFmpeg环境
    check_ffmpeg
    
    # 检查命令行参数
    if [[ $# -eq 0 ]]; then
        echo "使用方法:"
        echo "  单文件转换: $0 <输入文件> [输出文件]"
        echo "  批量转换:   $0 --batch <输入目录> [输出目录]"
        echo
        echo "示例:"
        echo "  $0 S-ZTCJ03DZ0043-8_data"
        echo "  $0 --batch ./input_files"
        exit 1
    fi
    
    # 处理批量转换
    if [[ "$1" == "--batch" ]]; then
        if [[ $# -lt 2 ]]; then
            log_error "批量转换需要指定输入目录"
            exit 1
        fi
        
        local input_dir="$2"
        local output_dir="${3:-output}"
        
        if [[ ! -d "$input_dir" ]]; then
            log_error "输入目录不存在: $input_dir"
            exit 1
        fi
        
        batch_convert "$input_dir" "$output_dir"
        
    else
        # 单文件转换
        local input_file="$1"
        local output_file="${2:-output/$(basename "$input_file" | sed 's/\.[^.]*$//')_audio.wav}"
        
        if [[ ! -f "$input_file" ]]; then
            log_error "输入文件不存在: $input_file"
            exit 1
        fi
        
        log_info "找到输入文件: $input_file"
        local file_size=$(stat -f%z "$input_file" 2>/dev/null || stat -c%s "$input_file" 2>/dev/null)
        log_info "文件大小: $(( file_size / 1024 )) KB"
        echo
        
        # 创建输出目录
        local output_dir=$(dirname "$output_file")
        mkdir -p "$output_dir"
        
        # 分析文件结构
        analyze_file "$input_file"
        
        # 尝试转换
        local conversion_methods=("standard" "forced" "enhanced" "raw_s16le" "raw_s16be" "raw_f32le")
        local converted=false
        
        for method in "${conversion_methods[@]}"; do
            log_info "尝试转换方法: $method"
            
            if convert_audio "$input_file" "$output_file" "$method"; then
                if verify_output "$output_file"; then
                    echo
                    echo "========================================"
                    log_success "转换成功完成！"
                    echo "========================================"
                    echo
                    converted=true
                    break
                else
                    log_warning "方法 '$method' 失败，尝试下一种方法..."
                    echo
                fi
            else
                log_warning "方法 '$method' 失败，尝试下一种方法..."
                echo
            fi
        done
        
        if [[ "$converted" == false ]]; then
            echo
            echo "========================================"
            log_error "所有转换方法都失败了"
            echo "========================================"
            echo
            echo "可能的原因:"
            echo "1. 输入文件格式不支持"
            echo "2. 文件可能损坏"
            echo "3. 需要特殊的转换参数"
            echo
            echo "建议:"
            echo "1. 检查输入文件是否完整"
            echo "2. 尝试使用其他音频转换工具"
            echo "3. 联系技术支持"
            exit 1
        fi
    fi
    
    echo
    log_success "转换过程完成"
}

# 执行主程序
main "$@"
