#!/bin/bash
# ================================================
# ARM32 Shared Python App - Smart Deploy/Upgrade Script
# Auto-detect package type, validate integrity, preview changes
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
    log_error "Root permission required, please use: sudo $0 $@"
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
    full)         echo "Full Package (Python + Apps)" ;;
    python-only)  echo "Python Upgrade Package" ;;
    app-only)     echo "App Incremental Package" ;;
    empty)        echo "Empty Package" ;;
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
  echo -e " ${BOLD}Installed Versions${NC}"
  echo -e "========================================"
  if [ -f "$VERSIONS_FILE" ]; then
    printf " %-20s %s\n" "Component" "Version"
    printf " %-20s %s\n" "----" "----"
    while IFS=: read -r comp ver; do
      printf " %-20s %s\n" "$comp" "$ver"
    done < "$VERSIONS_FILE"
  else
    log_warn "Version file not found: $VERSIONS_FILE"
  fi
  echo ""
}

backup_app() {
  local APP_DIR="$1"
  if [ -d "$APP_DIR" ]; then
    local OLD_VERSION=$(cat "$APP_DIR/VERSION" 2>/dev/null || echo "unknown")
    local BACKUP_DIR="${APP_DIR}.bak.$(date +%Y%m%d_%H%M%S)_v${OLD_VERSION}"
    log_info "Backup: $(basename $APP_DIR) ($OLD_VERSION) -> $(basename $BACKUP_DIR)"
    cp -a "$APP_DIR" "$BACKUP_DIR"
    touch "$BACKUP_DIR"
    find "$INSTALL_DIR" -maxdepth 1 -name "*.bak.*" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
  fi
}

install_shared_python() {
  log_step "Installing Shared Python"
  local NEW_DIR="${SHARED_PYTHON_DIR}.new"
  rm -rf "$NEW_DIR"
  mkdir -p "$NEW_DIR"

  tar xzf shared-python-base-arm32.tar.gz -C "$NEW_DIR/" --strip-components=1

  if [ ! -x "$NEW_DIR/bin/python3" ] && [ -x "$NEW_DIR/shared-python/bin/python3" ]; then
    log_warn "Detected legacy tar format, adjusting directory structure..."
    mv "$NEW_DIR/shared-python/"* "$NEW_DIR/" 2>/dev/null || true
    mv "$NEW_DIR/shared-python/".[!.]* "$NEW_DIR/" 2>/dev/null || true
    rm -rf "$NEW_DIR/shared-python"
  fi

  rm -f "$NEW_DIR/bin/pip"* 2>/dev/null || true
  if [ ! -x "$NEW_DIR/bin/python3" ]; then
    log_error "New Python validation failed: python3 not executable"
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
  log_info "Shared Python installed: $new_ver"
}

install_app() {
  local APP_TAR="$1"
  local APP_NAME=$(echo "$APP_TAR" | sed "s/-arm32.tar.gz//")
  local APP_DIR="${INSTALL_DIR}/${APP_NAME}"
  local NEW_DIR="${APP_DIR}.new"
  log_step "Installing app: $APP_NAME"
  rm -rf "$NEW_DIR"
  mkdir -p "$NEW_DIR"
  tar xzf "$APP_TAR" -C "$NEW_DIR/" --strip-components=1
  chmod +x "$NEW_DIR/run.sh" 2>/dev/null || true
  if [ ! -f "$NEW_DIR/VERSION" ]; then
    log_error "App validation failed: VERSION file missing"
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
  log_info "$APP_NAME installed: $new_ver -> Run: $APP_NAME"
}

uninstall_app() {
  local APP_NAME="$1"
  local APP_DIR="${INSTALL_DIR}/${APP_NAME}"
  if [ ! -d "$APP_DIR" ]; then
    log_error "App $APP_NAME not installed (directory $APP_DIR does not exist)"
    exit 1
  fi
  if [ "$APP_NAME" = "shared-python" ]; then
    log_error "Cannot uninstall shared-python via this command, please uninstall manually"
    log_error "Note: Uninstalling shared-python will break all dependent apps"
    exit 1
  fi
  local OLD_VERSION=$(cat "$APP_DIR/VERSION" 2>/dev/null || echo "unknown")
  log_step "Uninstalling app: $APP_NAME ($OLD_VERSION)"
  rm -f "/usr/local/bin/$APP_NAME" 2>/dev/null || true
  backup_app "$APP_DIR"
  rm -rf "$APP_DIR"
  if [ -f "$VERSIONS_FILE" ]; then
    local tmpfile=$(mktemp)
    grep -v "^${APP_NAME}:" "$VERSIONS_FILE" > "$tmpfile" || true
    mv "$tmpfile" "$VERSIONS_FILE"
  fi
  log_info "$APP_NAME ($OLD_VERSION) uninstalled"
}

verify_checksums() {
  if [ ! -f "$SCRIPT_DIR/checksums.txt" ]; then
    log_warn "checksums.txt not found, skipping integrity check"
    return 0
  fi
  log_step "Verifying package integrity (SHA256)"
  cd "$SCRIPT_DIR"
  if sha256sum -c checksums.txt 2>/dev/null; then
    log_info "All packages verified successfully"
  else
    log_error "Package verification failed! Files may be corrupted or tampered"
    log_error "Please re-download the deployment package"
    exit 1
  fi
}

validate_full_install() {
  if ! $HAS_PYTHON_PKG; then
    log_error "First-time install requires shared-python-base-arm32.tar.gz"
    log_error "Current package is app-only, please use full deployment package"
    return 1
  fi
  if [ ${#APP_TARS[@]} -eq 0 ]; then
    log_error "First-time install requires at least one app package"
    log_error "Current package is Python-only, please use full deployment package"
    return 1
  fi
  return 0
}

validate_python_upgrade() {
  if ! $HAS_PYTHON_PKG; then
    log_error "Upgrading shared-python requires shared-python-base-arm32.tar.gz"
    return 1
  fi
  if ! $PYTHON_INSTALLED; then
    log_error "Target machine does not have shared-python installed, cannot upgrade"
    log_error "Please use full deployment package for first-time installation"
    return 1
  fi
  return 0
}

validate_app_upgrade() {
  if ! $PYTHON_INSTALLED; then
    log_error "Target machine does not have shared-python installed, apps cannot run"
    log_error "Please use full deployment package for first-time installation"
    return 1
  fi
  if [ ${#APP_TARS[@]} -eq 0 ]; then
    log_error "No app upgrade packages found"
    return 1
  fi
  return 0
}

show_preview() {
  local pkg_type="$1"
  local is_first_install="$2"
  echo ""
  echo -e "========================================"
  echo -e " ${BOLD}Deployment Preview${NC}"
  echo -e "========================================"
  echo -e " Package Type: ${CYAN}$(get_package_type_label "$pkg_type")${NC}"
  if $is_first_install; then
    echo -e " System Status: ${YELLOW}Not Installed (First Deploy)${NC}"
  else
    echo -e " System Status: ${GREEN}Installed${NC}"
  fi
  echo ""
  echo -e " ${BOLD}Operations to be performed:${NC}"
  if $HAS_PYTHON_PKG; then
    if $PYTHON_INSTALLED; then
      local old_py_ver=$(read_installed_version "shared-python")
      local new_py_ver=$(read_version_from_tar "shared-python-base-arm32.tar.gz" "shared-python/VERSION")
      if [ "$old_py_ver" = "$new_py_ver" ]; then
        echo -e " ${CYAN}=${NC} Reinstall shared-python: $old_py_ver (same version)"
      else
        echo -e " ${YELLOW}*${NC} Upgrade shared-python: $old_py_ver -> ${GREEN}$new_py_ver${NC}"
      fi
    else
      local new_py_ver=$(read_version_from_tar "shared-python-base-arm32.tar.gz" "shared-python/VERSION")
      echo -e " ${GREEN}+${NC} Install shared-python: ${GREEN}$new_py_ver${NC}"
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
        echo -e " ${CYAN}=${NC} Reinstall $app_name: $old_ver (same version)"
      else
        echo -e " ${YELLOW}*${NC} Upgrade $app_name: $old_ver -> ${GREEN}$new_ver${NC}"
      fi
    else
      echo -e " ${GREEN}+${NC} Install $app_name: ${GREEN}$new_ver${NC}"
    fi
  done
  echo ""
}

show_help() {
  echo ""
  echo "ARM32 Shared Python App - Smart Deployment Script"
  echo ""
  echo "Usage:"
  echo " sudo bash $0                 # Smart mode"
  echo " sudo bash $0 --force         # Force mode"
  echo " sudo bash $0 -y              # Auto confirm"
  echo " sudo bash $0 --show-versions # Show installed versions"
  echo " sudo bash $0 --uninstall <app_name> # Uninstall specified app"
  echo " sudo bash $0 --clean-backup  # Clean backups"
  echo " sudo bash $0 --help          # Show help"
  echo ""
  exit 0
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f)   FORCE_MODE=true; shift ;;
    -y|--yes)     YES_MODE=true; shift ;;
    --uninstall)
      if [ -z "$2" ]; then
        log_error "--uninstall requires an app name"
        echo "Usage: sudo bash $0 --uninstall <app_name>"
        echo "View installed apps: sudo bash $0 --show-versions"
        exit 1
      fi
      check_root "$@"
      uninstall_app "$2"
      exit 0
      ;;
    --show-versions) scan_installed; show_versions; exit 0 ;;
    --clean-backup)
      echo "Cleaning backup files..."
      find "$INSTALL_DIR" -maxdepth 1 -name "*.bak.*" -type d -exec rm -rf {} + 2>/dev/null || true
      log_info "Backup cleanup completed"
      exit 0
      ;;
    --help|-h) show_help ;;
    *) log_error "Unknown parameter: $1"; show_help ;;
  esac
done

# --- Main Flow ---
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
    if $FIRST_INSTALL; then validate_full_install || exit 1; ACTION_LABEL="First-time Install"
    else validate_full_install || exit 1; ACTION_LABEL="Full Upgrade"
    fi ;;
  python-only)
    if $FIRST_INSTALL; then
      log_error "System does not have shared-python installed, Python-only package cannot perform first-time install"
      exit 1
    fi
    validate_python_upgrade || exit 1
    ACTION_LABEL="Python Upgrade" ;;
  app-only)
    if $FIRST_INSTALL; then
      log_error "System does not have shared-python installed, apps cannot run"
      exit 1
    fi
    validate_app_upgrade || exit 1
    if [ ${#APP_TARS[@]} -eq 1 ]; then
      ACTION_LABEL="App Upgrade ($(echo ${APP_TARS[0]} | sed 's/-arm32.tar.gz//'))"
    else
      ACTION_LABEL="App Upgrade (${#APP_TARS[@]} apps)"
    fi ;;
  empty)
    log_error "No valid installation packages found in current directory (*-arm32.tar.gz)"
    exit 1 ;;
esac

show_preview "$PKG_TYPE" "$FIRST_INSTALL"

if ! $FORCE_MODE && ! $YES_MODE; then
  if [ -t 0 ]; then
    read -p "Confirm $ACTION_LABEL? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then echo "Cancelled"; exit 0; fi
  else
    log_warn "Non-interactive terminal, use -y or --force to skip confirmation"
    exit 1
  fi
fi

echo ""
echo -e "========================================"
echo -e " ${BOLD}Starting: $ACTION_LABEL${NC}"
echo -e "========================================"

if $HAS_PYTHON_PKG; then install_shared_python; fi
for app_tar in "${APP_TARS[@]}"; do install_app "$app_tar"; done

echo ""
echo -e "========================================"
echo -e " ${GREEN}${BOLD}[OK] $ACTION_LABEL Completed!${NC}"
echo -e "========================================"
show_versions
