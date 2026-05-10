#!/bin/bash
# ================================================
# ARM32 共享 Python 应用 - 智能部署/升级脚本
# 自动识别包类型，校验合法性，预览变更
# ================================================
set -e

INSTALL_DIR="/opt"
SHARED_PYTHON_DIR="${INSTALL_DIR}/shared-python"
VERSIONS_FILE="${INSTALL_DIR}/versions"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

FORCE_MODE=false
YES_MODE=false

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}--- $1 ---${NC}"; }

check_root() {
  if [ "$(id -u)" -ne 0 ]; then
    log_error "需要 root 权限，请使用: sudo $0 $@"
    exit 1
  fi
}

read_version_from_tar() {
  local tar_file="$1"
  local inner_path="$2"
  tar xzf "$tar_file" -O "$inner_path" 2>/dev/null || echo "unknown"
}

read_installed_version() {
  local component="$1"
  local dir="${INSTALL_DIR}/${component}"
  if [ -f "$dir/VERSION" ]; then
    cat "$dir/VERSION"
  else
    echo "unknown"
  fi
}

HAS_PYTHON_PKG=false
APP_TARS=()

scan_package() {
  cd "$SCRIPT_DIR"
  if [ -f "shared-python-base-arm32.tar.gz" ]; then
    HAS_PYTHON_PKG=true
  fi
  for tar_file in *-arm32.tar.gz; do
    [ "$tar_file" = "shared-python-base-arm32.tar.gz" ] && continue
    [ ! -f "$tar_file" ] && continue
    APP_TARS+=("$tar_file")
  done
}

get_package_type() {
  if $HAS_PYTHON_PKG && [ ${#APP_TARS[@]} -gt 0 ]; then echo "full"
  elif $HAS_PYTHON_PKG && [ ${#APP_TARS[@]} -eq 0 ]; then echo "python-only"
  elif ! $HAS_PYTHON_PKG && [ ${#APP_TARS[@]} -gt 0 ]; then echo "app-only"
  else echo "empty"
  fi
}

get_package_type_label() {
  case "$1" in
    full)         echo "全量包 (Python + 应用)" ;;
    python-only)  echo "Python 升级包" ;;
    app-only)     echo "应用增量升级包" ;;
    empty)        echo "空包" ;;
  esac
}

PYTHON_INSTALLED=false
INSTALLED_APPS=()

scan_installed() {
  if [ -d "$SHARED_PYTHON_DIR" ] && [ -x "$SHARED_PYTHON_DIR/bin/python3" ]; then
    PYTHON_INSTALLED=true
  fi
  for app_dir in "${INSTALL_DIR}"/*/; do
    [ ! -d "$app_dir" ] && continue
    local name=$(basename "$app_dir")
    [ "$name" = "shared-python" ] && continue
    [[ "$name" == *.bak* ]] && continue
    if [ -f "$app_dir/run.sh" ]; then
      INSTALLED_APPS+=("$name")
    fi
  done
}

update_versions() {
  local component="$1"
  local version="$2"
  local tmpfile=$(mktemp)
  if [ -f "$VERSIONS_FILE" ]; then
    grep -v "^${component}:" "$VERSIONS_FILE" > "$tmpfile" || true
  else
    > "$tmpfile"
  fi
  echo "${component}:${version}" >> "$tmpfile"
  mv "$tmpfile" "$VERSIONS_FILE"
}

show_versions() {
  echo ""
  echo -e "========================================"
  echo -e " ${BOLD}当前工控机已安装版本${NC}"
  echo -e "========================================"
  if [ -f "$VERSIONS_FILE" ]; then
    printf " %-20s %s\n" "组件" "版本"
    printf " %-20s %s\n" "----" "----"
    while IFS=: read -r comp ver; do
      printf " %-20s %s\n" "$comp" "$ver"
    done < "$VERSIONS_FILE"
  else
    log_warn "未找到版本记录文件 $VERSIONS_FILE"
  fi
  echo ""
}

backup_app() {
  local APP_DIR="$1"
  if [ -d "$APP_DIR" ]; then
    local OLD_VERSION=$(cat "$APP_DIR/VERSION" 2>/dev/null || echo "unknown")
    local BACKUP_DIR="${APP_DIR}.bak.$(date +%Y%m%d_%H%M%S)_v${OLD_VERSION}"
    log_info "备份: $(basename $APP_DIR) ($OLD_VERSION) → $(basename $BACKUP_DIR)"
    cp -a "$APP_DIR" "$BACKUP_DIR"
    touch "$BACKUP_DIR"
    find "$INSTALL_DIR" -maxdepth 1 -name "*.bak.*" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
  fi
}

install_shared_python() {
  log_step "安装共享 Python"
  local NEW_DIR="${SHARED_PYTHON_DIR}.new"
  rm -rf "$NEW_DIR"
  mkdir -p "$NEW_DIR"

  # 解压到临时目录，去掉 shared-python/ 前缀
  tar xzf shared-python-base-arm32.tar.gz -C "$NEW_DIR/" --strip-components=1

  # [Fix #4] 兼容旧格式 tar 包 (不含 shared-python/ 前缀)
  if [ ! -x "$NEW_DIR/bin/python3" ] && [ -x "$NEW_DIR/shared-python/bin/python3" ]; then
    log_warn "检测到旧格式 tar 包，调整目录结构..."
    mv "$NEW_DIR/shared-python/"* "$NEW_DIR/" 2>/dev/null || true
    mv "$NEW_DIR/shared-python/".[!.]* "$NEW_DIR/" 2>/dev/null || true
    rm -rf "$NEW_DIR/shared-python"
  fi

  rm -f "$NEW_DIR/bin/pip"* 2>/dev/null || true
  if [ ! -x "$NEW_DIR/bin/python3" ]; then
    log_error "新 Python 环境校验失败: python3 不可执行"
    rm -rf "$NEW_DIR"
    exit 1
  fi
  if [ -d "$SHARED_PYTHON_DIR" ]; then
    backup_app "$SHARED_PYTHON_DIR"
    mv "$SHARED_PYTHON_DIR" "${SHARED_PYTHON_DIR}.old"
  fi
  mv "$NEW_DIR" "$SHARED_PYTHON_DIR"
  rm -rf "${SHARED_PYTHON_DIR}.old"
  local new_ver=$(cat "$SHARED_PYTHON_DIR/VERSION")
  update_versions "shared-python" "$new_ver"
  log_info "共享 Python 已安装: $new_ver"
}

install_app() {
  local APP_TAR="$1"
  local APP_NAME=$(echo "$APP_TAR" | sed "s/-arm32.tar.gz//")
  local APP_DIR="${INSTALL_DIR}/${APP_NAME}"
  local NEW_DIR="${APP_DIR}.new"
  log_step "安装应用: $APP_NAME"
  rm -rf "$NEW_DIR"
  mkdir -p "$NEW_DIR"
  tar xzf "$APP_TAR" -C "$NEW_DIR/" --strip-components=1
  chmod +x "$NEW_DIR/run.sh" 2>/dev/null || true
  if [ ! -f "$NEW_DIR/VERSION" ]; then
    log_error "新应用校验失败: VERSION 文件缺失"
    rm -rf "$NEW_DIR"
    exit 1
  fi
  if [ -d "$APP_DIR" ]; then
    backup_app "$APP_DIR"
    mv "$APP_DIR" "${APP_DIR}.old"
  fi
  mv "$NEW_DIR" "$APP_DIR"
  rm -rf "${APP_DIR}.old"
  rm -f "/usr/local/bin/$APP_NAME" 2>/dev/null || true
  ln -sf "$APP_DIR/run.sh" "/usr/local/bin/$APP_NAME"
  local new_ver=$(cat "$APP_DIR/VERSION")
  update_versions "$APP_NAME" "$new_ver"
  log_info "$APP_NAME 已安装: $new_ver → 运行: $APP_NAME"
}

verify_checksums() {
  if [ ! -f "$SCRIPT_DIR/checksums.txt" ]; then
    log_warn "未找到 checksums.txt，跳过完整性校验"
    return 0
  fi
  log_step "校验安装包完整性 (SHA256)"
  cd "$SCRIPT_DIR"
  if sha256sum -c checksums.txt 2>/dev/null; then
    log_info "所有安装包校验通过"
  else
    log_error "安装包校验失败！文件可能已损坏或被篡改"
    log_error "请重新下载部署包"
    exit 1
  fi
}

validate_full_install() {
  if ! $HAS_PYTHON_PKG; then
    log_error "首次安装需要 shared-python-base-arm32.tar.gz"
    log_error "当前包为应用增量包，请使用全量部署包"
    return 1
  fi
  if [ ${#APP_TARS[@]} -eq 0 ]; then
    log_error "首次安装需要至少一个应用包"
    log_error "当前包为 Python 升级包，请使用全量部署包"
    return 1
  fi
  return 0
}

validate_python_upgrade() {
  if ! $HAS_PYTHON_PKG; then
    log_error "升级共享 Python 需要 shared-python-base-arm32.tar.gz"
    return 1
  fi
  if ! $PYTHON_INSTALLED; then
    log_error "目标机未安装 shared-python，无法执行升级"
    log_error "请先使用全量部署包完成首次安装"
    return 1
  fi
  return 0
}

validate_app_upgrade() {
  if ! $PYTHON_INSTALLED; then
    log_error "目标机未安装 shared-python，应用无法运行"
    log_error "请先使用全量部署包完成首次安装"
    return 1
  fi
  if [ ${#APP_TARS[@]} -eq 0 ]; then
    log_error "未找到任何应用升级包"
    return 1
  fi
  return 0
}

show_preview() {
  local pkg_type="$1"
  local is_first_install="$2"
  echo ""
  echo -e "========================================"
  echo -e " ${BOLD}📦 部署预览${NC}"
  echo -e "========================================"
  echo -e " 包类型: ${CYAN}$(get_package_type_label "$pkg_type")${NC}"
  if $is_first_install; then
    echo -e " 系统状态: ${YELLOW}未安装 (首次部署)${NC}"
  else
    echo -e " 系统状态: ${GREEN}已安装${NC}"
  fi
  echo ""
  echo -e " ${BOLD}即将执行的操作:${NC}"
  if $HAS_PYTHON_PKG; then
    if $PYTHON_INSTALLED; then
      local old_py_ver=$(read_installed_version "shared-python")
      local new_py_ver=$(read_version_from_tar "shared-python-base-arm32.tar.gz" "shared-python/VERSION")
      if [ "$old_py_ver" = "$new_py_ver" ]; then
        echo -e " ${CYAN}≡${NC} 重装 shared-python: $old_py_ver (版本未变)"
      else
        echo -e " ${YELLOW}↻${NC} 升级 shared-python: $old_py_ver → ${GREEN}$new_py_ver${NC}"
      fi
    else
      local new_py_ver=$(read_version_from_tar "shared-python-base-arm32.tar.gz" "shared-python/VERSION")
      echo -e " ${GREEN}✚${NC} 安装 shared-python: ${GREEN}$new_py_ver${NC}"
    fi
  fi
  for app_tar in "${APP_TARS[@]}"; do
    local app_name=$(echo "$app_tar" | sed "s/-arm32.tar.gz//")
    local new_ver=$(read_version_from_tar "$app_tar" "$app_name/VERSION")
    local is_installed=false
    for installed in "${INSTALLED_APPS[@]}"; do
      if [ "$installed" = "$app_name" ]; then is_installed=true; break; fi
    done
    if $is_installed; then
      local old_ver=$(read_installed_version "$app_name")
      if [ "$old_ver" = "$new_ver" ]; then
        echo -e " ${CYAN}≡${NC} 重装 $app_name: $old_ver (版本未变)"
      else
        echo -e " ${YELLOW}↻${NC} 升级 $app_name: $old_ver → ${GREEN}$new_ver${NC}"
      fi
    else
      echo -e " ${GREEN}✚${NC} 安装 $app_name: ${GREEN}$new_ver${NC}"
    fi
  done
  echo ""
}

show_help() {
  echo ""
  echo "ARM32 共享 Python 应用 - 智能部署脚本"
  echo ""
  echo "Usage:"
  echo " sudo bash $0                 # 智能模式"
  echo " sudo bash $0 --force         # 强制模式"
  echo " sudo bash $0 -y              # 自动确认"
  echo " sudo bash $0 --show-versions # 查看已安装版本"
  echo " sudo bash $0 --clean-backup  # 清理备份"
  echo " sudo bash $0 --help          # 显示帮助"
  echo ""
  exit 0
}

# ─── 参数解析 ───
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f)   FORCE_MODE=true; shift ;;
    -y|--yes)     YES_MODE=true; shift ;;
    --show-versions) scan_installed; show_versions; exit 0 ;;
    --clean-backup)
      echo "清理备份文件..."
      find "$INSTALL_DIR" -maxdepth 1 -name "*.bak.*" -type d -exec rm -rf {} + 2>/dev/null || true
      log_info "备份清理完成"
      exit 0
      ;;
    --help|-h) show_help ;;
    *) log_error "未知参数: $1"; show_help ;;
  esac
done

# ─── 主流程 ───
check_root "$@"
scan_package
scan_installed
verify_checksums

PKG_TYPE=$(get_package_type)
FIRST_INSTALL=false
if ! $PYTHON_INSTALLED; then FIRST_INSTALL=true; fi

echo ""
case "$PKG_TYPE" in
  full)
    if $FIRST_INSTALL; then validate_full_install || exit 1; ACTION_LABEL="首次安装"
    else validate_full_install || exit 1; ACTION_LABEL="全量升级"
    fi ;;
  python-only)
    if $FIRST_INSTALL; then
      log_error "系统未安装 shared-python，仅 Python 升级包无法完成首次安装"
      exit 1
    fi
    validate_python_upgrade || exit 1
    ACTION_LABEL="Python 升级" ;;
  app-only)
    if $FIRST_INSTALL; then
      log_error "系统未安装 shared-python，应用无法运行"
      exit 1
    fi
    validate_app_upgrade || exit 1
    if [ ${#APP_TARS[@]} -eq 1 ]; then
      ACTION_LABEL="应用增量升级 ($(echo ${APP_TARS[0]} | sed 's/-arm32.tar.gz//'))"
    else
      ACTION_LABEL="应用增量升级 (${#APP_TARS[@]} 个应用)"
    fi ;;
  empty)
    log_error "当前目录未找到任何有效的安装包 (*-arm32.tar.gz)"
    exit 1 ;;
esac

show_preview "$PKG_TYPE" "$FIRST_INSTALL"

if ! $FORCE_MODE && ! $YES_MODE; then
  if [ -t 0 ]; then
    read -p "确认执行 $ACTION_LABEL? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then echo "已取消"; exit 0; fi
  else
    log_warn "非交互式终端，使用 -y 或 --force 跳过确认"
    exit 1
  fi
fi

echo ""
echo -e "========================================"
echo -e " ${BOLD}开始执行: $ACTION_LABEL${NC}"
echo -e "========================================"

if $HAS_PYTHON_PKG; then install_shared_python; fi
for app_tar in "${APP_TARS[@]}"; do install_app "$app_tar"; done

echo ""
echo -e "========================================"
echo -e " ${GREEN}${BOLD}✅ $ACTION_LABEL 完成！${NC}"
echo -e "========================================"
show_versions
