#!/usr/bin/env bash

set -euo pipefail

# Qoder CLI Installation Script v2.0.0
# - Version-managed storage: ~/.qoder/bin/qodercli/qodercli-[version]  
# - User-space installation: ~/.local/bin/qodercli (no sudo required)
# - Automatic PATH configuration for supported shells

BASE_URL="https://qoder-ide.oss-ap-southeast-1.aliyuncs.com/qodercli"
FORCE=0
VERBOSE=0
INSTALL_DIR="$HOME/.qoder"
BIN_DIR="$INSTALL_DIR/bin/qodercli"
LOCAL_BIN_DIR="$HOME/.local/bin"
BIN_LINK="$LOCAL_BIN_DIR/qodercli"

usage() {
  cat <<EOF >&2
Qoder CLI Installation Script

USAGE:
  curl -fsSL ${BASE_URL}/install.sh | bash
  curl -fsSL ${BASE_URL}/install.sh | bash -s -- [OPTIONS]

OPTIONS:
  --force                Force overwrite existing installation
  --verbose              Show detailed installation information
  -h, --help            Show this help message

EXAMPLES:
  # Standard installation
  curl -fsSL ${BASE_URL}/install.sh | bash

  # Force reinstall with verbose output
  curl -fsSL ${BASE_URL}/install.sh | bash -s -- --force --verbose

NOTE:
  For Windows users, please download the install.ps1 or install.bat scripts
  from the repository and run them directly.
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    *)
      echo "Error: Unknown option $1" >&2
      usage
      exit 1
      ;;
  esac
done

detect_os_arch() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  
  if [[ "$arch" == "aarch64" ]]; then
    arch="arm64"
  fi
  if [[ "$arch" == "x86_64" ]]; then
    arch="amd64"
  fi
  
  echo "$os $arch"
}

download() {
  local url="$1" output="$2"
  local max_retries=3
  local retry_count=0
  
  while [[ $retry_count -lt $max_retries ]]; do
    if [[ $retry_count -gt 0 ]]; then
      echo "Retry attempt $retry_count/$max_retries..." >&2
      sleep 2
    fi
    
    if command -v curl >/dev/null 2>&1; then
      if curl -fsSL --retry 2 --connect-timeout 30 --max-time 300 "$url" -o "$output"; then
        return 0
      fi
    elif command -v wget >/dev/null 2>&1; then
      if wget -q --tries=2 --connect-timeout=30 --read-timeout=300 "$url" -O "$output"; then
        return 0
      fi
    else
      echo "Error: Neither curl nor wget is available" >&2
      exit 1
    fi
    
    # Clean up partial download on failure
    rm -f "$output" 2>/dev/null || true
    retry_count=$((retry_count + 1))
  done
  
  echo "Error: Failed to download $url after $max_retries attempts" >&2
  if command -v curl >/dev/null 2>&1; then
    echo "Using curl with retries and timeouts" >&2
  elif command -v wget >/dev/null 2>&1; then
    echo "Using wget with retries and timeouts" >&2
  fi
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: $1 is required but not installed" >&2
    exit 1
  fi
}

detect_shell() {
  local shell=""
  
  # Check environment variables
  if [[ -n "${SHELL:-}" ]]; then
    shell="$(basename "$SHELL")"
  elif [[ -n "${ZSH_VERSION:-}" ]]; then
    shell="zsh"
  elif [[ -n "${BASH_VERSION:-}" ]]; then
    shell="bash"
  elif [[ -n "${FISH_VERSION:-}" ]]; then
    shell="fish"
  fi
  
  # Normalize shell names
  case "${shell:-unknown}" in
    bash|bash.exe) echo "bash" ;;
    zsh|zsh.exe) echo "zsh" ;;
    fish|fish.exe) echo "fish" ;;
    ash|dash|sh) echo "sh" ;;
    *) echo "unknown" ;;
  esac
}

is_local_bin_in_path() {
  [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]
}

get_shell_config() {
  local shell="$1"
  case "$shell" in
    bash)
      for config in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
        if [[ -f "$config" ]]; then
          echo "$config"
          return
        fi
      done
      ;;
    zsh)
      for config in "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.profile"; do
        if [[ -f "$config" ]]; then
          echo "$config"
          return
        fi
      done
      ;;
    fish)
      if [[ -f "$HOME/.config/fish/config.fish" ]]; then
        echo "$HOME/.config/fish/config.fish"
      fi
      ;;
    sh)
      for config in "$HOME/.profile" "$HOME/.bash_profile"; do
        if [[ -f "$config" ]]; then
          echo "$config"
          return
        fi
      done
      ;;
  esac
}

inject_path() {
  local shell="$1"
  
  if is_local_bin_in_path; then
    if [[ $VERBOSE -eq 1 ]]; then
      echo "==> ~/.local/bin already in PATH"
    fi
    return 0
  fi
  
  if [[ "$shell" == "unknown" ]]; then
    echo ""
    echo "⚠️  Unknown shell detected. Please manually add to your shell config:"
    echo "   export PATH=\"\$PATH:$HOME/.local/bin\""
    echo ""
    return 1
  fi
  
  local config_file
  config_file="$(get_shell_config "$shell")"
  
  if [[ -z "$config_file" ]]; then
    echo "==> Warning: No shell config file found. Please manually add:"
    echo "==> export PATH=\"\$PATH:$HOME/.local/bin\""
    return 1
  fi
  
  # Check if config file is writable, create parent directory if needed
  local config_dir
  config_dir="$(dirname "$config_file")"
  if [[ ! -d "$config_dir" ]]; then
    if ! mkdir -p "$config_dir" 2>/dev/null; then
      echo "==> Error: Cannot create config directory $config_dir" >&2
      echo "==> Please manually add: export PATH=\"\$PATH:$HOME/.local/bin\"" >&2
      return 1
    fi
  fi
  
  # Test if we can write to the config file
  if [[ -f "$config_file" ]] && [[ ! -w "$config_file" ]]; then
    echo "==> Error: Config file $config_file is not writable" >&2
    echo "==> Please manually add: export PATH=\"\$PATH:$HOME/.local/bin\"" >&2
    return 1
  fi
  
  # Test write permission by trying to create/touch the file
  if ! touch "$config_file" 2>/dev/null; then
    echo "==> Error: Cannot write to config file $config_file" >&2
    echo "==> Please manually add: export PATH=\"\$PATH:$HOME/.local/bin\"" >&2
    return 1
  fi
  
  local path_export
  if [[ "$shell" == "fish" ]]; then
    path_export="set -gx PATH \$PATH $HOME/.local/bin"
  else
    path_export="export PATH=\"\$PATH:$HOME/.local/bin\""
  fi
  
  # Check if already configured with precise regex
  if grep -Eqs '^[[:space:]]*(export[[:space:]]+PATH=.*\$PATH.*\$HOME|set[[:space:]]+-gx[[:space:]]+PATH.*\$HOME)[[:space:]]*\.local/bin' "$config_file"; then
    if [[ $VERBOSE -eq 1 ]]; then
      echo "==> PATH already configured in $config_file"
    fi
    return 0
  fi
  
  # Add PATH export with error handling
  if ! {
    echo ""
    echo "# Added by Qoder CLI installer"
    echo "$path_export"
  } >> "$config_file" 2>/dev/null; then
    echo "==> Error: Failed to write to config file $config_file" >&2
    echo "==> Please manually add: $path_export" >&2
    return 1
  fi
  
  echo "==> Added ~/.local/bin to PATH in $config_file"
  echo "==> To apply changes immediately, run: source $config_file"
  echo "==> Or restart your terminal"
}


install_binary() {
  local bin_name="$1"
  local version="$2"
  local tmpdir="$3"
  
  local version_bin="$BIN_DIR/qodercli-$version"
  
  if [[ -e "$version_bin" && "$FORCE" != "1" ]]; then
    echo "Error: Version $version already exists. Use --force to overwrite." >&2
    exit 1
  fi
  
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Installing to $BIN_DIR"
  fi
  
  # Create BIN_DIR with proper error handling
  if ! mkdir -p "$BIN_DIR" 2>/dev/null; then
    echo "Error: Cannot create installation directory $BIN_DIR" >&2
    echo "Please check directory permissions and try again" >&2
    exit 1
  fi
  
  # Move binary with error handling
  if ! mv "$tmpdir/$bin_name" "$version_bin" 2>/dev/null; then
    echo "Error: Failed to move binary to $version_bin" >&2
    echo "Please check directory permissions and available disk space" >&2
    exit 1
  fi
  
  # Set executable permission with error handling
  if ! chmod +x "$version_bin" 2>/dev/null; then
    echo "Warning: Failed to set executable permission on $version_bin" >&2
    echo "You may need to manually run: chmod +x $version_bin" >&2
  fi

  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Installed to: $version_bin"
  fi
  
  # Create installation source marker with error handling
  local source_file="$BIN_DIR/.qodercli-install-resource"
  if ! echo "curl-bash" > "$source_file" 2>/dev/null; then
    if [[ $VERBOSE -eq 1 ]]; then
      echo "==> Warning: Failed to create install source marker" >&2
    fi
  elif [[ $VERBOSE -eq 1 ]]; then
    echo "==> Created install source marker: $source_file"
  fi
  
  # Create LOCAL_BIN_DIR with proper error handling
  if ! mkdir -p "$LOCAL_BIN_DIR" 2>/dev/null; then
    echo "Warning: Cannot create local bin directory $LOCAL_BIN_DIR" >&2
    echo "Binary installed at: $version_bin" >&2
    echo "You may need to manually create the directory and symlink" >&2
    return 0
  fi
  
  # Remove existing link
  rm -f "$BIN_LINK" 2>/dev/null || true
  
  # Try symlink first, fallback to copy
  if ln -s "$version_bin" "$BIN_LINK" 2>/dev/null; then
    if [[ $VERBOSE -eq 1 ]]; then
      echo "==> Created symlink: $BIN_LINK -> $version_bin"
    fi
  else
    if cp "$version_bin" "$BIN_LINK" 2>/dev/null && chmod +x "$BIN_LINK" 2>/dev/null; then
      if [[ $VERBOSE -eq 1 ]]; then
        echo "==> Created copy: $BIN_LINK"
      fi
    else
      echo "Warning: Failed to create binary link at $BIN_LINK" >&2
      echo "Binary available at: $version_bin" >&2
      echo "You may need to manually create a symlink or add $BIN_DIR to your PATH" >&2
    fi
  fi
}

# Global variables for cleanup function
TMP_DIR=""

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR" 2>/dev/null || true
  fi
}

main() {
  # Early Windows detection - exit on Windows systems
  local os_name
  os_name="$(uname -s | tr '[:upper:]' '[:lower:]')"
  if [[ "$os_name" == *"mingw"* || "$os_name" == *"cygwin"* || "$os_name" == *"msys"* ]]; then
    echo "❌ Windows system detected." >&2
    echo "" >&2
    echo "This installer is designed for Unix-like systems (Linux/macOS)." >&2
    echo "For Windows support:" >&2
    echo "  • Use the provided install.ps1 or install.bat scripts" >&2
    echo "  • Use npm: npm install -g @qoder-ai/qodercli" >&2
    echo "  • Use WSL (Windows Subsystem for Linux)" >&2
    echo "  • Download binaries directly from releases page" >&2
    echo "" >&2
    exit 1
  fi
  
  # Create temporary directory for all operations
  TMP_DIR="$(mktemp -d -t qoder-install.XXXXXX)"
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Created temporary directory: $TMP_DIR"
  fi
  
  # Setup cleanup trap for production-grade error handling  
  # Handle both normal exit and signal interruptions
  trap cleanup EXIT INT TERM
  
  local shell
  shell="$(detect_shell)"
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Detected shell: $shell"
  fi
  
  local os arch
  read -r os arch < <(detect_os_arch)

  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Detected platform: $os/$arch"
  fi
  
  # Fetch manifest
  local manifest_url="$BASE_URL/channels/manifest.json"
  local manifest_file="$TMP_DIR/qoder-manifest.json"
  
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Fetching release information..."
  fi
  download "$manifest_url" "$manifest_file"
  
  # Parse manifest using awk/sed for minimal dependencies (no jq required)
  # This matches the actual manifest structure used by the update system
  local manifest_json
  manifest_json="$(cat "$manifest_file")"
  
  # Extract version from manifest
  local version
  version=$(printf '%s' "$manifest_json" | sed -n 's/.*"latest"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  
  if [[ -z "$version" ]]; then
    echo "Error: Cannot parse version from manifest" >&2
    exit 1
  fi

  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Latest version: $version"
  fi

  # Find matching file entry for current platform
  local entry
  entry=$(printf '%s' "$manifest_json" | awk -v os="$os" -v arch="$arch" '
    BEGIN { RS="{"; FS="," }
    /"os"[[:space:]]*:[[:space:]]*"/ && /"arch"[[:space:]]*:[[:space:]]*"/ {
      if ($0 ~ "\"os\"[[:space:]]*:[[:space:]]*\"" os "\"" && $0 ~ "\"arch\"[[:space:]]*:[[:space:]]*\"" arch "\"") {
        print "{" $0
        exit
      }
    }
  ')
  
  if [[ -z "$entry" ]]; then
    echo "Error: No matching release found in manifest for ${os}/${arch}" >&2
    exit 1
  fi

  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Found binary for $os/$arch"
  fi
  
  # Extract URL and checksum from the matched entry
  local download_url checksum
  download_url=$(printf '%s' "$entry" | sed -n 's/.*"url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  checksum=$(printf '%s' "$entry" | sed -n 's/.*"sha256"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  
  if [[ -z "$download_url" ]]; then
    echo "Error: Missing download URL in manifest for ${os}/${arch}" >&2
    exit 1
  fi
  
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Downloading Qoder CLI $version..."
  fi

  local archive_filename
  archive_filename=$(basename "$download_url")
  local archive_file="$TMP_DIR/$archive_filename"

  # Check required extraction tool based on file extension
  if [[ "$archive_filename" =~ \.zip$ ]]; then
    require_cmd unzip
  elif [[ "$archive_filename" =~ \.(tar\.gz|tgz)$ ]]; then
    require_cmd tar
  else
    echo "Error: Unsupported archive format: $archive_filename" >&2
    exit 1
  fi
  
  download "$download_url" "$archive_file"
  
  # Verify file was downloaded and has reasonable size
  if [[ ! -f "$archive_file" ]]; then
    echo "Error: Downloaded file $archive_file not found" >&2
    exit 1
  fi
  
  local file_size
  file_size=$(wc -c < "$archive_file" 2>/dev/null || echo "0")
  if [[ "$file_size" -lt 1024 ]]; then
    echo "Error: Downloaded file is too small ($file_size bytes), likely corrupted" >&2
    echo "URL: $download_url" >&2
    exit 1
  fi
  
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Downloaded file size: $file_size bytes"
  fi
  
  # Verify checksum
  if [[ -n "$checksum" ]]; then
    if [[ $VERBOSE -eq 1 ]]; then
      echo "==> Verifying checksum..."
    fi
    local checksum_verified=0
    local checksum_file="$TMP_DIR/$(basename "$archive_file").sha256"
    
    # Create checksum file for verification (more reliable than echo | -c)
    # Use basename to ensure -c works correctly with relative paths
    printf '%s  %s\n' "$checksum" "$(basename "$archive_file")" > "$checksum_file"
    
    # Run verification in the same directory as the files
    if command -v shasum >/dev/null 2>&1; then
      if (cd "$TMP_DIR" && shasum -a 256 -c "$(basename "$checksum_file")") >/dev/null 2>&1; then
        checksum_verified=1
      fi
    elif command -v sha256sum >/dev/null 2>&1; then
      if (cd "$TMP_DIR" && sha256sum -c "$(basename "$checksum_file")") >/dev/null 2>&1; then
        checksum_verified=1
      fi
    else
      echo "Warning: No checksum verification tool available (shasum or sha256sum)" >&2
    fi
    
    if [[ $checksum_verified -eq 1 ]]; then
      if [[ $VERBOSE -eq 1 ]]; then
        echo "==> Checksum verified"
      fi
    else
      echo "Error: Checksum verification failed" >&2
      echo "Expected: $checksum" >&2
      echo "File: $(basename "$archive_file")" >&2
      
      # Show actual checksum for debugging
      local actual_checksum=""
      if command -v shasum >/dev/null 2>&1; then
        actual_checksum=$(shasum -a 256 "$archive_file" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
      elif command -v sha256sum >/dev/null 2>&1; then
        actual_checksum=$(sha256sum "$archive_file" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
      fi
      
      if [[ -n "$actual_checksum" && "$actual_checksum" != "unknown" ]]; then
        echo "Actual:   $actual_checksum" >&2
      fi
      
      echo "File size: $(wc -c < "$archive_file" 2>/dev/null || echo 'unknown') bytes" >&2
      echo "Try running the installer again to re-download the file." >&2
      
      exit 1
    fi
  fi
  
  # Extract archive
  if [[ $VERBOSE -eq 1 ]]; then
    echo "==> Extracting archive..."
  fi
  local extract_dir="$TMP_DIR/extract"
  mkdir -p "$extract_dir"
  # 根据文件扩展名选择解压方式
  if [[ "$archive_filename" =~ \.zip$ ]]; then
    unzip -q "$archive_file" -d "$extract_dir"
  elif [[ "$archive_filename" =~ \.(tar\.gz|tgz)$ ]]; then
    tar -xzf "$archive_file" -C "$extract_dir"
  else
    echo "Error: Unsupported archive format: $archive_filename" >&2
    exit 1
  fi
  
  local bin_name="qodercli"
  if [[ "$os" == "windows" ]]; then
    bin_name="qodercli.exe"
  fi
  
  if [[ ! -f "$extract_dir/$bin_name" ]]; then
    echo "Error: Binary $bin_name not found in archive" >&2
    exit 1
  fi
  
  install_binary "$bin_name" "$version" "$extract_dir"
  
  # Configure PATH (cleanup handled by trap)
  inject_path "$shell"
  
  echo ""
  echo "🎉 Qoder CLI $version installed successfully!"
  echo ""
  if [[ -f "$BIN_LINK" ]]; then
    echo "Get started: qodercli --help"
  else
    echo "Get started: $BIN_DIR/qodercli-$version --help"
  fi
}

main "$@"