#!/bin/bash
# FFmpeg安装脚本 (Linux/macOS版本)
# 自动检测系统并安装FFmpeg
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
    echo "FFmpeg自动安装脚本"
    echo "支持 Linux, macOS"
    echo "========================================"
    echo
}

# 检测系统类型
detect_system() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        SYSTEM="linux"
        log_info "检测到Linux系统"
        
        # 检测Linux发行版
        if [[ -f /etc/os-release ]]; then
            source /etc/os-release
            DISTRO="$ID"
            log_info "检测到发行版: $PRETTY_NAME"
        elif [[ -f /etc/redhat-release ]]; then
            DISTRO="rhel"
            log_info "检测到Red Hat系列发行版"
        elif [[ -f /etc/debian_version ]]; then
            DISTRO="debian"
            log_info "检测到Debian系列发行版"
        else
            DISTRO="unknown"
            log_warning "无法识别Linux发行版"
        fi
        
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        SYSTEM="macos"
        log_info "检测到macOS系统"
        
        # 检测macOS版本
        MACOS_VERSION=$(sw_vers -productVersion)
        log_info "macOS版本: $MACOS_VERSION"
        
    else
        SYSTEM="unknown"
        log_error "不支持的操作系统: $OSTYPE"
        exit 1
    fi
    
    echo
}

# 检查FFmpeg是否已安装
check_existing_ffmpeg() {
    log_info "检查FFmpeg是否已安装..."
    
    if command -v ffmpeg >/dev/null 2>&1; then
        local version=$(ffmpeg -version | head -n 1)
        log_success "FFmpeg已安装: $version"
        
        if command -v ffprobe >/dev/null 2>&1; then
            log_success "ffprobe也已安装"
        else
            log_warning "ffprobe未安装，但FFmpeg可用"
        fi
        
        echo
        read -p "FFmpeg已安装，是否重新安装？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "跳过安装"
            exit 0
        fi
    else
        log_info "FFmpeg未安装，开始安装..."
    fi
    
    echo
}

# Linux安装FFmpeg
install_linux() {
    log_info "开始Linux FFmpeg安装..."
    
    case "$DISTRO" in
        "ubuntu"|"debian")
            install_ubuntu_debian
            ;;
        "centos"|"rhel"|"fedora")
            install_centos_rhel_fedora
            ;;
        "arch"|"manjaro")
            install_arch
            ;;
        "opensuse"|"sles")
            install_opensuse
            ;;
        *)
            install_generic_linux
            ;;
    esac
}

# Ubuntu/Debian安装
install_ubuntu_debian() {
    log_info "使用apt安装FFmpeg (Ubuntu/Debian)..."
    
    # 更新包列表
    log_info "更新包列表..."
    sudo apt update
    
    # 安装FFmpeg
    log_info "安装FFmpeg..."
    sudo apt install -y ffmpeg
    
    log_success "FFmpeg安装完成"
}

# CentOS/RHEL/Fedora安装
install_centos_rhel_fedora() {
    log_info "使用包管理器安装FFmpeg (CentOS/RHEL/Fedora)..."
    
    if command -v dnf >/dev/null 2>&1; then
        # Fedora/CentOS 8+
        log_info "使用dnf安装FFmpeg..."
        sudo dnf install -y ffmpeg
    elif command -v yum >/dev/null 2>&1; then
        # CentOS 7/RHEL 7
        log_info "使用yum安装FFmpeg..."
        
        # 添加EPEL仓库
        log_info "添加EPEL仓库..."
        sudo yum install -y epel-release
        
        # 安装FFmpeg
        sudo yum install -y ffmpeg
    else
        log_error "未找到支持的包管理器 (dnf/yum)"
        return 1
    fi
    
    log_success "FFmpeg安装完成"
}

# Arch Linux安装
install_arch() {
    log_info "使用pacman安装FFmpeg (Arch Linux)..."
    
    # 更新包数据库
    log_info "更新包数据库..."
    sudo pacman -Sy
    
    # 安装FFmpeg
    log_info "安装FFmpeg..."
    sudo pacman -S --noconfirm ffmpeg
    
    log_success "FFmpeg安装完成"
}

# openSUSE安装
install_opensuse() {
    log_info "使用zypper安装FFmpeg (openSUSE)..."
    
    # 更新包列表
    log_info "更新包列表..."
    sudo zypper refresh
    
    # 安装FFmpeg
    log_info "安装FFmpeg..."
    sudo zypper install -y ffmpeg
    
    log_success "FFmpeg安装完成"
}

# 通用Linux安装
install_generic_linux() {
    log_warning "无法识别Linux发行版，尝试通用安装方法..."
    
    # 尝试Snap安装
    if command -v snap >/dev/null 2>&1; then
        log_info "使用Snap安装FFmpeg..."
        sudo snap install ffmpeg
        log_success "FFmpeg安装完成 (Snap)"
        return 0
    fi
    
    # 尝试AppImage
    log_info "尝试下载FFmpeg AppImage..."
    local ffmpeg_dir="$HOME/.local/bin"
    mkdir -p "$ffmpeg_dir"
    
    local appimage_url="https://github.com/eugeneware/ffmpeg-static/releases/download/b4.4.1/ffmpeg-linux-x64"
    local appimage_path="$ffmpeg_dir/ffmpeg"
    
    if command -v wget >/dev/null 2>&1; then
        wget -O "$appimage_path" "$appimage_url"
    elif command -v curl >/dev/null 2>&1; then
        curl -L -o "$appimage_path" "$appimage_url"
    else
        log_error "未找到wget或curl，无法下载FFmpeg"
        return 1
    fi
    
    chmod +x "$appimage_path"
    
    # 添加到PATH
    if [[ ":$PATH:" != *":$ffmpeg_dir:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    log_success "FFmpeg安装完成 (AppImage)"
    log_info "请重新启动终端或运行: source ~/.bashrc"
}

# macOS安装FFmpeg
install_macos() {
    log_info "开始macOS FFmpeg安装..."
    
    # 检查Homebrew
    if command -v brew >/dev/null 2>&1; then
        log_info "使用Homebrew安装FFmpeg..."
        
        # 更新Homebrew
        log_info "更新Homebrew..."
        brew update
        
        # 安装FFmpeg
        log_info "安装FFmpeg..."
        brew install ffmpeg
        
        log_success "FFmpeg安装完成 (Homebrew)"
        return 0
    fi
    
    # 检查MacPorts
    if command -v port >/dev/null 2>&1; then
        log_info "使用MacPorts安装FFmpeg..."
        
        # 更新MacPorts
        log_info "更新MacPorts..."
        sudo port selfupdate
        
        # 安装FFmpeg
        log_info "安装FFmpeg..."
        sudo port install ffmpeg
        
        log_success "FFmpeg安装完成 (MacPorts)"
        return 0
    fi
    
    # 手动安装
    log_warning "未找到Homebrew或MacPorts，尝试手动安装..."
    
    # 检查是否有Xcode命令行工具
    if ! command -v xcode-select >/dev/null 2>&1; then
        log_error "需要安装Xcode命令行工具"
        log_info "请运行: xcode-select --install"
        return 1
    fi
    
    # 下载预编译版本
    log_info "下载FFmpeg预编译版本..."
    local ffmpeg_dir="/usr/local/bin"
    local ffmpeg_url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    local temp_dir=$(mktemp -d)
    
    cd "$temp_dir"
    
    if command -v curl >/dev/null 2>&1; then
        curl -L -o ffmpeg.zip "$ffmpeg_url"
    else
        log_error "需要curl来下载FFmpeg"
        return 1
    fi
    
    unzip ffmpeg.zip
    sudo mv ffmpeg "$ffmpeg_dir/"
    
    # 清理临时文件
    cd /
    rm -rf "$temp_dir"
    
    log_success "FFmpeg安装完成 (手动安装)"
}

# 验证安装
verify_installation() {
    log_info "验证FFmpeg安装..."
    
    if command -v ffmpeg >/dev/null 2>&1; then
        local version=$(ffmpeg -version | head -n 1)
        log_success "FFmpeg安装成功: $version"
        
        if command -v ffprobe >/dev/null 2>&1; then
            log_success "ffprobe也可用"
        else
            log_warning "ffprobe不可用"
        fi
        
        return 0
    else
        log_error "FFmpeg安装失败"
        return 1
    fi
}

# 显示使用说明
show_usage() {
    echo
    echo "========================================"
    echo "FFmpeg安装完成！"
    echo "========================================"
    echo
    echo "使用方法:"
    echo "  检查版本: ffmpeg -version"
    echo "  转换音频: ffmpeg -i input.dat -vn -map 0:a -c:a pcm_s16le output.wav"
    echo "  分析文件: ffprobe -v quiet -show_streams -i input.dat"
    echo
    echo "或使用我们的转换脚本:"
    echo "  ./convert_audio.sh input_file.dat"
    echo "  python3 audio_converter.py input_file.dat"
    echo
}

# 主程序
main() {
    show_header
    
    # 检测系统
    detect_system
    
    # 检查现有安装
    check_existing_ffmpeg
    
    # 根据系统类型安装
    case "$SYSTEM" in
        "linux")
            install_linux
            ;;
        "macos")
            install_macos
            ;;
        *)
            log_error "不支持的操作系统"
            exit 1
            ;;
    esac
    
    # 验证安装
    if verify_installation; then
        show_usage
    else
        log_error "安装验证失败"
        exit 1
    fi
}

# 执行主程序
main "$@"
