#!/bin/bash
# 批量音频转换脚本 (Linux/macOS版本)
# 批量转换多个音频文件
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
    echo "批量音频转换工具 (Linux/macOS版本)"
    echo "========================================"
    echo
}

# 检查FFmpeg环境
check_environment() {
    log_info "检查FFmpeg环境..."
    
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_error "FFmpeg未安装"
        echo "请先运行: ./install_ffmpeg.sh"
        exit 1
    fi
    
    log_success "FFmpeg环境检查通过"
    echo
}

# 查找输入文件
find_input_files() {
    local input_dir="$1"
    local file_patterns=("${@:2}")
    
    if [[ ${#file_patterns[@]} -eq 0 ]]; then
        file_patterns=("*_data" "*.dat" "*.bin" "*.raw")
    fi
    
    local files=()
    
    for pattern in "${file_patterns[@]}"; do
        while IFS= read -r -d '' file; do
            files+=("$file")
        done < <(find "$input_dir" -maxdepth 1 -type f -name "$pattern" -print0 2>/dev/null)
    done
    
    # 去重
    local unique_files=()
    for file in "${files[@]}"; do
        local found=false
        for unique_file in "${unique_files[@]}"; do
            if [[ "$file" == "$unique_file" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == false ]]; then
            unique_files+=("$file")
        fi
    done
    
    echo "${unique_files[@]}"
}

# 转换单个文件
convert_single_file() {
    local input_file="$1"
    local output_file="$2"
    local method="$3"
    
    case "$method" in
        "standard")
            ffmpeg -probesize 10M -analyzeduration 10M \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "forced")
            ffmpeg -f mpeg \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "enhanced")
            ffmpeg -probesize 20M -analyzeduration 20M \
                -i "$input_file" \
                -vn -map 0:a -c:a pcm_s16le -ac 2 -ar 44100 \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_s16le")
            ffmpeg -f s16le -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_s16be")
            ffmpeg -f s16be -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        "raw_f32le")
            ffmpeg -f f32le -ar 44100 -ac 1 \
                -i "$input_file" \
                -c:a pcm_s16le \
                -y "$output_file" 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
    
    return $?
}

# 验证输出文件
verify_output_file() {
    local output_file="$1"
    
    if [[ -f "$output_file" ]]; then
        local file_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
        if [[ $file_size -gt 0 ]]; then
            return 0
        fi
    fi
    
    return 1
}

# 批量转换
batch_convert() {
    local input_dir="$1"
    local output_dir="$2"
    local file_patterns=("${@:3}")
    
    log_info "开始批量转换..."
    log_info "输入目录: $input_dir"
    log_info "输出目录: $output_dir"
    
    if [[ ${#file_patterns[@]} -gt 0 ]]; then
        log_info "文件模式: ${file_patterns[*]}"
    fi
    
    echo
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    # 查找输入文件
    local input_files=($(find_input_files "$input_dir" "${file_patterns[@]}"))
    
    if [[ ${#input_files[@]} -eq 0 ]]; then
        log_warning "未找到可转换的文件"
        return 0
    fi
    
    log_info "找到 ${#input_files[@]} 个文件需要转换"
    echo
    
    # 转换统计
    local total_count=${#input_files[@]}
    local success_count=0
    local failed_count=0
    local failed_files=()
    
    # 转换方法列表
    local conversion_methods=("standard" "forced" "enhanced" "raw_s16le" "raw_s16be" "raw_f32le")
    
    # 转换每个文件
    for i in "${!input_files[@]}"; do
        local input_file="${input_files[$i]}"
        local filename=$(basename "$input_file")
        local output_file="$output_dir/${filename%.*}_audio.wav"
        
        local file_num=$((i + 1))
        log_info "[$file_num/$total_count] 转换文件: $filename"
        
        local converted=false
        
        # 尝试不同的转换方法
        for method in "${conversion_methods[@]}"; do
            if convert_single_file "$input_file" "$output_file" "$method"; then
                if verify_output_file "$output_file"; then
                    log_success "转换成功: $filename (方法: $method)"
                    ((success_count++))
                    converted=true
                    break
                else
                    log_warning "方法 $method 输出验证失败，尝试下一种方法"
                fi
            else
                log_warning "方法 $method 转换失败，尝试下一种方法"
            fi
        done
        
        if [[ "$converted" == false ]]; then
            log_error "所有转换方法都失败: $filename"
            ((failed_count++))
            failed_files+=("$filename")
        fi
        
        echo
    done
    
    # 显示结果
    echo "========================================"
    log_info "批量转换完成"
    echo "  总文件数: $total_count"
    echo "  成功: $success_count"
    echo "  失败: $failed_count"
    echo "  成功率: $(( success_count * 100 / total_count ))%"
    echo "========================================"
    
    if [[ $failed_count -gt 0 ]]; then
        echo
        log_warning "失败的文件:"
        for failed_file in "${failed_files[@]}"; do
            echo "  - $failed_file"
        done
        echo
        log_info "建议:"
        echo "  1. 检查失败文件的格式"
        echo "  2. 尝试手动转换"
        echo "  3. 使用Python转换工具: python3 audio_converter.py"
    fi
}

# 显示帮助信息
show_help() {
    echo "使用方法:"
    echo "  $0 <输入目录> [输出目录] [文件模式...]"
    echo
    echo "参数说明:"
    echo "  输入目录    必需，包含要转换文件的目录"
    echo "  输出目录    可选，默认为 'output'"
    echo "  文件模式    可选，支持的通配符模式，默认为 '*_data *.dat *.bin *.raw'"
    echo
    echo "示例:"
    echo "  $0 ./input_files"
    echo "  $0 ./input_files ./converted"
    echo "  $0 ./input_files ./converted '*.dat' '*.bin'"
    echo
    echo "支持的文件模式:"
    echo "  *_data      - 以_data结尾的文件"
    echo "  *.dat       - .dat扩展名文件"
    echo "  *.bin       - .bin扩展名文件"
    echo "  *.raw       - .raw扩展名文件"
    echo "  *           - 所有文件"
    echo
}

# 主程序
main() {
    show_header
    
    # 检查FFmpeg环境
    check_environment
    
    # 检查命令行参数
    if [[ $# -lt 1 ]]; then
        show_help
        exit 1
    fi
    
    local input_dir="$1"
    local output_dir="${2:-output}"
    local file_patterns=("${@:3}")
    
    # 检查输入目录
    if [[ ! -d "$input_dir" ]]; then
        log_error "输入目录不存在: $input_dir"
        exit 1
    fi
    
    # 执行批量转换
    batch_convert "$input_dir" "$output_dir" "${file_patterns[@]}"
}

# 执行主程序
main "$@"
