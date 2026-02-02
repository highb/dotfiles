#!/usr/bin/env bash
set -euo pipefail

# Dotfiles manager - simple, idempotent, cross-platform
# Uses GNU Stow for symlinking, supports brew/apt/pacman

# Resolve symlinks to get actual repo location
DOTFILES_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"
BIN_DIR="$HOME/bin"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#-----------------------------------------------------------------------------
# Utility functions
#-----------------------------------------------------------------------------

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

detect_platform() {
    case "$(uname -s)" in
        Darwin) echo "darwin" ;;
        Linux)
            if [[ -f /etc/os-release ]]; then
                . /etc/os-release
                case "$ID" in
                    ubuntu|debian|pop) echo "ubuntu" ;;
                    arch|manjaro|endeavouros) echo "arch" ;;
                    *) echo "linux" ;;
                esac
            else
                echo "linux"
            fi
            ;;
        *) echo "unknown" ;;
    esac
}

detect_package_manager() {
    local platform="$1"
    case "$platform" in
        darwin) echo "brew" ;;
        ubuntu) echo "apt" ;;
        arch)   echo "pacman" ;;
        *)      echo "unknown" ;;
    esac
}

command_exists() {
    command -v "$1" &>/dev/null
}

ensure_stow() {
    if ! command_exists stow; then
        log_error "GNU Stow is not installed. Install it first:"
        case "$(detect_platform)" in
            darwin) echo "  brew install stow" ;;
            ubuntu) echo "  sudo apt install stow" ;;
            arch)   echo "  sudo pacman -S stow" ;;
        esac
        exit 1
    fi
}

#-----------------------------------------------------------------------------
# Package management
#-----------------------------------------------------------------------------

get_package_name() {
    local generic_name="$1"
    local pkg_manager="$2"
    local mappings_file="$DOTFILES_DIR/packages/mappings.txt"

    if [[ -f "$mappings_file" ]]; then
        local line
        line=$(grep "^${generic_name}:" "$mappings_file" 2>/dev/null || true)
        if [[ -n "$line" ]]; then
            case "$pkg_manager" in
                brew)   echo "$line" | cut -d: -f2 ;;
                apt)    echo "$line" | cut -d: -f3 ;;
                pacman) echo "$line" | cut -d: -f4 ;;
            esac
            return
        fi
    fi
    # No mapping found, return generic name
    echo "$generic_name"
}

load_packages() {
    local platform="$1"
    local packages=()

    # Load common packages
    if [[ -f "$DOTFILES_DIR/packages/common.txt" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            line="${line%%#*}"  # Remove comments
            line="${line// /}"  # Remove whitespace
            [[ -n "$line" ]] && packages+=("$line")
        done < "$DOTFILES_DIR/packages/common.txt"
    fi

    # Load platform-specific packages
    local platform_file="$DOTFILES_DIR/packages/${platform}.txt"
    if [[ -f "$platform_file" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            line="${line%%#*}"
            line="${line// /}"
            [[ -n "$line" ]] && packages+=("$line")
        done < "$platform_file"
    fi

    printf '%s\n' "${packages[@]}"
}

install_package() {
    local pkg="$1"
    local pkg_manager="$2"
    local actual_pkg
    actual_pkg=$(get_package_name "$pkg" "$pkg_manager")

    [[ -z "$actual_pkg" || "$actual_pkg" == "-" ]] && {
        log_warn "Package '$pkg' not available for $pkg_manager, skipping"
        return 0
    }

    log_info "Installing $actual_pkg via $pkg_manager..."
    case "$pkg_manager" in
        brew)
            brew install "$actual_pkg" 2>/dev/null || brew upgrade "$actual_pkg" 2>/dev/null || true
            ;;
        apt)
            sudo apt-get install -y "$actual_pkg"
            ;;
        pacman)
            sudo pacman -S --noconfirm --needed "$actual_pkg"
            ;;
    esac
}

uninstall_package() {
    local pkg="$1"
    local pkg_manager="$2"
    local actual_pkg
    actual_pkg=$(get_package_name "$pkg" "$pkg_manager")

    [[ -z "$actual_pkg" || "$actual_pkg" == "-" ]] && return 0

    log_info "Uninstalling $actual_pkg via $pkg_manager..."
    case "$pkg_manager" in
        brew)
            brew uninstall "$actual_pkg" 2>/dev/null || true
            ;;
        apt)
            sudo apt-get remove -y "$actual_pkg"
            ;;
        pacman)
            sudo pacman -Rs --noconfirm "$actual_pkg" 2>/dev/null || true
            ;;
    esac
}

cmd_packages() {
    local action="${1:-install}"
    local platform
    platform=$(detect_platform)
    local pkg_manager
    pkg_manager=$(detect_package_manager "$platform")

    if [[ "$pkg_manager" == "unknown" ]]; then
        log_error "Unknown package manager for platform: $platform"
        exit 1
    fi

    log_info "Platform: $platform, Package manager: $pkg_manager"

    # Update package manager
    if [[ "$action" == "install" ]]; then
        log_info "Updating package manager..."
        case "$pkg_manager" in
            brew)   brew update ;;
            apt)    sudo apt-get update ;;
            pacman) sudo pacman -Sy ;;
        esac
    fi

    local packages
    packages=$(load_packages "$platform")

    if [[ -z "$packages" ]]; then
        log_warn "No packages defined"
        return 0
    fi

    while IFS= read -r pkg; do
        if [[ "$action" == "install" ]]; then
            install_package "$pkg" "$pkg_manager"
        else
            uninstall_package "$pkg" "$pkg_manager"
        fi
    done <<< "$packages"

    log_ok "Packages ${action}ed"
}

#-----------------------------------------------------------------------------
# Dotfiles management (stow)
#-----------------------------------------------------------------------------

prompt_conflict() {
    local target="$1"
    local source="$2"

    echo ""
    log_warn "Conflict: $target already exists"
    echo "  Source: $source"
    echo "  Target: $target"
    echo ""
    echo "Options:"
    echo "  [o] Overwrite (backup existing to $BACKUP_DIR)"
    echo "  [s] Skip"
    echo "  [d] Diff (show differences)"
    echo "  [q] Quit"
    echo ""

    while true; do
        read -rp "Choice [o/s/d/q]: " choice
        case "$choice" in
            o|O)
                mkdir -p "$BACKUP_DIR"
                mv "$target" "$BACKUP_DIR/"
                log_info "Backed up to $BACKUP_DIR/$(basename "$target")"
                return 0
                ;;
            s|S)
                return 1
                ;;
            d|D)
                if command_exists diff; then
                    diff -u "$target" "$source" || true
                else
                    log_warn "diff not available"
                fi
                ;;
            q|Q)
                exit 0
                ;;
            *)
                echo "Invalid choice"
                ;;
        esac
    done
}

stow_package() {
    local pkg_dir="$1"
    local pkg_name
    pkg_name=$(basename "$pkg_dir")
    local stow_dir
    stow_dir=$(dirname "$pkg_dir")

    log_info "Stowing $pkg_name..."

    # First, simulate to check for conflicts
    local conflicts
    conflicts=$(stow -d "$stow_dir" -t "$HOME" -n "$pkg_name" 2>&1 || true)

    if echo "$conflicts" | grep -q "existing target"; then
        # Parse conflicts and handle each
        while IFS= read -r line; do
            if [[ "$line" =~ existing\ target\ is\ neither\ a\ link\ nor\ a\ directory:\ (.+) ]]; then
                local target="$HOME/${BASH_REMATCH[1]}"
                local source="$pkg_dir/${BASH_REMATCH[1]}"
                if ! prompt_conflict "$target" "$source"; then
                    log_warn "Skipping $pkg_name"
                    return 0
                fi
            fi
        done <<< "$conflicts"
    fi

    # Actually stow
    stow -d "$stow_dir" -t "$HOME" "$pkg_name"
    log_ok "Stowed $pkg_name"
}

unstow_package() {
    local pkg_dir="$1"
    local pkg_name
    pkg_name=$(basename "$pkg_dir")
    local stow_dir
    stow_dir=$(dirname "$pkg_dir")

    log_info "Unstowing $pkg_name..."
    stow -d "$stow_dir" -t "$HOME" -D "$pkg_name" 2>/dev/null || true
    log_ok "Unstowed $pkg_name"
}

cmd_dotfiles() {
    local action="${1:-install}"
    local platform
    platform=$(detect_platform)

    ensure_stow

    # Determine which platform dirs to use
    local platform_dir="linux"
    [[ "$platform" == "darwin" ]] && platform_dir="darwin"

    local dirs=("$DOTFILES_DIR/dotfiles/common" "$DOTFILES_DIR/dotfiles/$platform_dir")

    for dir in "${dirs[@]}"; do
        [[ ! -d "$dir" ]] && continue

        for pkg in "$dir"/*/; do
            [[ ! -d "$pkg" ]] && continue
            if [[ "$action" == "install" ]]; then
                stow_package "$pkg"
            else
                unstow_package "$pkg"
            fi
        done
    done

    log_ok "Dotfiles ${action}ed"
}

#-----------------------------------------------------------------------------
# Scripts management
#-----------------------------------------------------------------------------

link_self() {
    local action="${1:-install}"
    local target="$BIN_DIR/dotfiles"

    if [[ "$action" == "install" ]]; then
        mkdir -p "$BIN_DIR"
        if [[ -e "$target" && ! -L "$target" ]]; then
            if ! prompt_conflict "$target" "$DOTFILES_DIR/setup.sh"; then
                return 0
            fi
        fi
        ln -sf "$DOTFILES_DIR/setup.sh" "$target"
        log_ok "Linked dotfiles → $target"
    else
        if [[ -L "$target" ]]; then
            rm "$target"
            log_ok "Unlinked dotfiles"
        fi
    fi
}

cmd_scripts() {
    local action="${1:-install}"
    local platform
    platform=$(detect_platform)

    local platform_dir="linux"
    [[ "$platform" == "darwin" ]] && platform_dir="darwin"

    local dirs=("$DOTFILES_DIR/scripts/common" "$DOTFILES_DIR/scripts/$platform_dir")

    if [[ "$action" == "install" ]]; then
        mkdir -p "$BIN_DIR"
    fi

    for dir in "${dirs[@]}"; do
        [[ ! -d "$dir" ]] && continue

        for script in "$dir"/*; do
            [[ ! -f "$script" ]] && continue
            local name
            name=$(basename "$script")
            local target="$BIN_DIR/$name"

            if [[ "$action" == "install" ]]; then
                if [[ -e "$target" && ! -L "$target" ]]; then
                    if ! prompt_conflict "$target" "$script"; then
                        continue
                    fi
                fi
                ln -sf "$script" "$target"
                chmod +x "$script"
                log_ok "Linked $name → $target"
            else
                if [[ -L "$target" ]]; then
                    rm "$target"
                    log_ok "Unlinked $name"
                fi
            fi
        done
    done

    log_ok "Scripts ${action}ed"
}

#-----------------------------------------------------------------------------
# Hoover - pull existing files into repo
#-----------------------------------------------------------------------------

cmd_add() {
    local type=""
    local source=""
    local platform="common"

    # Parse arguments
    for arg in "$@"; do
        case "$arg" in
            --darwin) platform="darwin" ;;
            --linux)  platform="linux" ;;
            config|script) type="$arg" ;;
            *) source="$arg" ;;
        esac
    done

    if [[ -z "$source" ]]; then
        log_error "Usage: add [config|script] <path> [--darwin|--linux]"
        exit 1
    fi

    # Expand path relative to home if needed
    if [[ "$source" == "~/"* ]]; then
        source="${source/#\~/$HOME}"
    elif [[ "$source" != "/"* ]]; then
        # Relative path - check if it's relative to home
        if [[ -e "$HOME/$source" ]]; then
            source="$HOME/$source"
        elif [[ -e "$source" ]]; then
            source="$(realpath "$source")"
        fi
    fi

    if [[ ! -e "$source" ]]; then
        log_error "Source does not exist: $source"
        exit 1
    fi

    source=$(realpath "$source")

    # Infer type if not specified
    if [[ -z "$type" ]]; then
        if [[ "$source" == "$HOME/bin/"* || "$source" == */bin/* ]]; then
            type="script"
        else
            type="config"
        fi
        log_info "Inferred type: $type"
    fi

    case "$type" in
        config)
            local rel_path="${source#$HOME/}"
            local pkg_name
            # Determine package name from path
            local first_component
            first_component=$(echo "$rel_path" | cut -d/ -f1)
            if [[ "$first_component" == ".config" || "$first_component" == ".local" ]]; then
                # For .config/foo or .local/foo, use foo as package name
                pkg_name=$(echo "$rel_path" | cut -d/ -f2)
            else
                # For dotfiles like .gitconfig, use the name without leading dot
                pkg_name="${first_component#.}"
            fi
            local dest_dir="$DOTFILES_DIR/dotfiles/$platform/$pkg_name"
            local dest="$dest_dir/$rel_path"

            mkdir -p "$(dirname "$dest")"

            if [[ -d "$source" ]]; then
                cp -r "$source" "$(dirname "$dest")/"
            else
                cp "$source" "$dest"
            fi

            log_ok "Added config: $source → $dest"
            log_info "Run 'dotfiles dotfiles' to create symlinks"
            ;;
        script)
            local name
            name=$(basename "$source")
            local dest="$DOTFILES_DIR/scripts/$platform/$name"

            mkdir -p "$(dirname "$dest")"
            cp "$source" "$dest"
            chmod +x "$dest"

            log_ok "Added script: $source → $dest"
            log_info "Run 'dotfiles scripts' to create symlinks"
            ;;
    esac
}

#-----------------------------------------------------------------------------
# Git helpers
#-----------------------------------------------------------------------------

cmd_save() {
    local message="${1:-}"

    cd "$DOTFILES_DIR"

    if [[ -z $(git status --porcelain) ]]; then
        log_info "Nothing to commit"
        return 0
    fi

    git add -A

    if [[ -z "$message" ]]; then
        log_info "Changes to commit:"
        git status --short
        echo ""
        read -rp "Commit message: " message
        [[ -z "$message" ]] && {
            log_error "Commit message required"
            exit 1
        }
    fi

    git commit -m "$message"
    log_ok "Committed"
}

cmd_push() {
    cd "$DOTFILES_DIR"
    git push
    log_ok "Pushed"
}

cmd_sync() {
    local message="${1:-}"
    cmd_save "$message"
    cmd_push
}

#-----------------------------------------------------------------------------
# Status
#-----------------------------------------------------------------------------

cmd_status() {
    local platform
    platform=$(detect_platform)
    local pkg_manager
    pkg_manager=$(detect_package_manager "$platform")

    echo ""
    echo "Platform: $platform"
    echo "Package manager: $pkg_manager"
    echo ""

    echo "=== Packages ==="
    local packages
    packages=$(load_packages "$platform")
    if [[ -n "$packages" ]]; then
        while IFS= read -r pkg; do
            local actual_pkg
            actual_pkg=$(get_package_name "$pkg" "$pkg_manager")
            if command_exists "$pkg" || command_exists "$actual_pkg"; then
                echo -e "  ${GREEN}✓${NC} $pkg"
            else
                echo -e "  ${RED}✗${NC} $pkg"
            fi
        done <<< "$packages"
    else
        echo "  (none defined)"
    fi
    echo ""

    echo "=== Dotfiles ==="
    local platform_dir="linux"
    [[ "$platform" == "darwin" ]] && platform_dir="darwin"

    for dir in "$DOTFILES_DIR/dotfiles/common" "$DOTFILES_DIR/dotfiles/$platform_dir"; do
        [[ ! -d "$dir" ]] && continue
        for pkg in "$dir"/*/; do
            [[ ! -d "$pkg" ]] && continue
            local name
            name=$(basename "$pkg")
            echo -e "  ${GREEN}✓${NC} $name ($(basename "$(dirname "$pkg")"))"
        done
    done
    echo ""

    echo "=== Scripts ==="
    # Check self-link
    if [[ -L "$BIN_DIR/dotfiles" ]]; then
        echo -e "  ${GREEN}✓${NC} dotfiles (self)"
    else
        echo -e "  ${YELLOW}○${NC} dotfiles (not linked)"
    fi
    for dir in "$DOTFILES_DIR/scripts/common" "$DOTFILES_DIR/scripts/$platform_dir"; do
        [[ ! -d "$dir" ]] && continue
        for script in "$dir"/*; do
            [[ ! -f "$script" ]] && continue
            local name
            name=$(basename "$script")
            if [[ -L "$BIN_DIR/$name" ]]; then
                echo -e "  ${GREEN}✓${NC} $name"
            else
                echo -e "  ${YELLOW}○${NC} $name (not linked)"
            fi
        done
    done
    echo ""

    echo "=== Git Status ==="
    cd "$DOTFILES_DIR"
    git status --short
    echo ""
}

#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------

usage() {
    cat <<EOF
Dotfiles Manager

Usage: $(basename "$0") <command> [args]

Commands:
  install             Install packages + dotfiles + scripts
  uninstall           Uninstall packages + dotfiles + scripts

  packages            Install packages only
  packages uninstall  Uninstall packages only

  dotfiles            Stow dotfiles only
  dotfiles uninstall  Unstow dotfiles only

  scripts             Link scripts to ~/bin only
  scripts uninstall   Unlink scripts only

  add <path> [--darwin|--linux]
                      Copy file into repo (auto-detects config vs script)
  add config <path>   Explicitly add as config
  add script <path>   Explicitly add as script

  save [message]      Git add + commit (prompts for message if not provided)
  push                Git push
  sync [message]      Save + push

  status              Show installation status

Examples:
  ./setup.sh install
  ./setup.sh add ~/.config/nvim           # auto-detects as config
  ./setup.sh add ~/bin/myscript           # auto-detects as script
  ./setup.sh add ~/.config/foo --darwin   # platform-specific
  ./setup.sh sync "Add nvim config"
EOF
}

main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        install)
            cmd_packages install
            cmd_dotfiles install
            cmd_scripts install
            link_self install
            ;;
        uninstall)
            link_self uninstall
            cmd_scripts uninstall
            cmd_dotfiles uninstall
            cmd_packages uninstall
            ;;
        packages)
            cmd_packages "${1:-install}"
            ;;
        dotfiles)
            cmd_dotfiles "${1:-install}"
            ;;
        scripts)
            cmd_scripts "${1:-install}"
            ;;
        add)
            [[ $# -lt 1 ]] && {
                log_error "Usage: add [config|script] <path> [--darwin|--linux]"
                exit 1
            }
            cmd_add "$@"
            ;;
        save)
            cmd_save "${1:-}"
            ;;
        push)
            cmd_push
            ;;
        sync)
            cmd_sync "${1:-}"
            ;;
        status)
            cmd_status
            ;;
        -h|--help|help|"")
            usage
            ;;
        *)
            log_error "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
