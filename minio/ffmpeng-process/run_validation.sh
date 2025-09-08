#!/bin/bash
# 音频数据验证工具启动脚本 (Linux/macOS版本)
# 作者：AI助手
# 版本：2.0

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

# 默认参数
DATA_FILE="S-ZTCJ03DZ0043-8&1756105438662&1_data"
META_FILE="S-ZTCJ03DZ0043-8&1756105438662&1_data.meta"
BASIC_ONLY=false
ADVANCED_ONLY=false
HELP=false

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

# 显示帮助信息
show_help() {
    echo -e "${CYAN}音频数据验证工具启动脚本 (Linux/macOS版本)${NC}"
    echo
    echo "使用方法:"
    echo "  $0 [选项]"
    echo
    echo "选项:"
    echo "  -d, --data-file <文件名>     指定数据文件名"
    echo "  -m, --meta-file <文件名>     指定元数据文件名"
    echo "  -b, --basic-only            仅运行基础验证工具"
    echo "  -a, --advanced-only         仅运行高级验证工具"
    echo "  -h, --help                  显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0"
    echo "  $0 -d my_data -m my_data.meta"
    echo "  $0 --basic-only"
    echo "  $0 --advanced-only"
    echo
}

# 解析命令行参数
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--data-file)
                DATA_FILE="$2"
                shift 2
                ;;
            -m|--meta-file)
                META_FILE="$2"
                shift 2
                ;;
            -b|--basic-only)
                BASIC_ONLY=true
                shift
                ;;
            -a|--advanced-only)
                ADVANCED_ONLY=true
                shift
                ;;
            -h|--help)
                HELP=true
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 检查Python环境
check_python() {
    log_info "检查Python环境..."
    
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$(python3 --version 2>&1)
        log_success "Python环境检查通过: $PYTHON_VERSION"
        return 0
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
        PYTHON_VERSION=$(python --version 2>&1)
        log_success "Python环境检查通过: $PYTHON_VERSION"
        return 0
    else
        log_error "未检测到Python环境"
        log_warning "请先安装Python 3.7或更高版本"
        log_info "Linux: sudo apt install python3 (Ubuntu/Debian)"
        log_info "macOS: brew install python3"
        return 1
    fi
}

# 检查文件是否存在
check_files() {
    log_info "检查必需文件..."
    
    local data_exists=false
    local meta_exists=false
    
    if [[ -f "$DATA_FILE" ]]; then
        local file_size=$(stat -f%z "$DATA_FILE" 2>/dev/null || stat -c%s "$DATA_FILE" 2>/dev/null)
        local file_size_mb=$((file_size / 1024 / 1024))
        log_success "数据文件检查通过: $DATA_FILE ($file_size_mb MB)"
        data_exists=true
    else
        log_error "未找到数据文件: $DATA_FILE"
    fi
    
    if [[ -f "$META_FILE" ]]; then
        local file_size=$(stat -f%z "$META_FILE" 2>/dev/null || stat -c%s "$META_FILE" 2>/dev/null)
        local file_size_kb=$((file_size / 1024))
        log_success "元数据文件检查通过: $META_FILE ($file_size_kb KB)"
        meta_exists=true
    else
        log_error "未找到元数据文件: $META_FILE"
    fi
    
    if [[ "$data_exists" == false || "$meta_exists" == false ]]; then
        log_warning "请确保所有必需文件都在当前目录下"
        return 1
    fi
    
    return 0
}

# 运行验证工具
run_validation() {
    local script_name="$1"
    local description="$2"
    
    log_info "开始运行$description..."
    echo "=================================================="
    
    local start_time=$(date +%s)
    local result=$($PYTHON_CMD "$script_name" "$DATA_FILE" "$META_FILE" 2>&1)
    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo
    log_success "$description 执行完成，耗时: ${duration} 秒"
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "$description 执行成功"
    else
        log_error "$description 执行失败，退出码: $exit_code"
    fi
    
    return $exit_code
}

# 显示报告文件
show_report_files() {
    log_info "生成的报告文件:"
    echo "------------------------------"
    
    local report_files=(
        "validation_report.txt:基础验证报告"
        "detailed_validation_report.txt:详细验证报告"
        "validation_results.json:JSON格式结果"
        "audio_validation.log:基础验证日志"
        "advanced_audio_validation.log:高级验证日志"
    )
    
    for file_info in "${report_files[@]}"; do
        local filename="${file_info%%:*}"
        local description="${file_info##*:}"
        
        if [[ -f "$filename" ]]; then
            local file_size=$(stat -f%z "$filename" 2>/dev/null || stat -c%s "$filename" 2>/dev/null)
            local file_size_kb=$((file_size / 1024))
            log_success "$filename ($file_size_kb KB) - $description"
        else
            log_error "$filename - $description"
        fi
    done
}

# 主程序
main() {
    echo "========================================"
    echo -e "${CYAN}音频数据验证工具启动脚本 (Linux/macOS版本)${NC}"
    echo "========================================"
    echo
    
    # 解析命令行参数
    parse_arguments "$@"
    
    # 显示帮助信息
    if [[ "$HELP" == true ]]; then
        show_help
        exit 0
    fi
    
    # 检查Python环境
    if ! check_python; then
        exit 1
    fi
    
    # 检查文件是否存在
    if ! check_files; then
        exit 1
    fi
    
    # 显示当前工作目录
    log_info "当前工作目录: $(pwd)"
    echo
    
    # 运行验证工具
    local basic_exit_code=0
    local advanced_exit_code=0
    
    if [[ "$ADVANCED_ONLY" == false ]]; then
        run_validation "audio_data_validator.py" "基础验证工具"
        basic_exit_code=$?
    fi
    
    if [[ "$BASIC_ONLY" == false ]]; then
        run_validation "advanced_audio_validator.py" "高级验证工具"
        advanced_exit_code=$?
    fi
    
    # 显示报告文件
    show_report_files
    
    # 总结
    echo
    log_success "验证完成！"
    
    if [[ $basic_exit_code -eq 0 && $advanced_exit_code -eq 0 ]]; then
        log_success "所有验证工具执行成功"
    else
        log_warning "部分验证工具执行失败，请查看日志文件"
    fi
    
    echo
    log_info "按回车键退出..."
    read -r
}

# 执行主程序
main "$@"
