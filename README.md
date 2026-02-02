# Dotfiles

Simple, idempotent dotfiles manager using GNU Stow.

## Bootstrap (new machine)

```bash
git clone https://github.com/highb/dotfiles.git ~/.config/dotfiles && ~/.config/dotfiles/setup.sh install
```

## Quick Start

```bash
# Install everything (packages + dotfiles + scripts + ~/bin/dotfiles symlink)
./setup.sh install

# After install, use from anywhere:
dotfiles status
dotfiles sync "updated nvim config"

# Or install components separately
./setup.sh packages
./setup.sh dotfiles
./setup.sh scripts

# Check status
./setup.sh status
```

## Directory Structure

```
dotfiles/
├── packages/           # Package definitions
│   ├── common.txt      # Packages for all platforms
│   ├── darwin.txt      # macOS-specific (brew)
│   ├── ubuntu.txt      # Ubuntu/Debian (apt)
│   ├── arch.txt        # Arch Linux (pacman)
│   └── mappings.txt    # Cross-platform name mappings
├── dotfiles/           # Config files (managed by stow)
│   ├── common/         # All platforms
│   ├── darwin/         # macOS-specific
│   └── linux/          # Linux-specific
├── scripts/            # Scripts → ~/bin
│   ├── common/
│   ├── darwin/
│   └── linux/
└── setup.sh
```

## Adding Configs

### Hoover existing configs into repo

```bash
# Add a config (type auto-detected)
dotfiles add ~/.config/nvim
dotfiles add ~/.gitconfig

# Platform-specific
dotfiles add ~/.config/foo --darwin

# Explicit type (if auto-detection is wrong)
dotfiles add config ~/some/path
```

### Manual structure

Configs go in `dotfiles/<platform>/<package-name>/` and mirror the home directory structure:

```
dotfiles/common/git/.gitconfig        → ~/.gitconfig
dotfiles/common/nvim/.config/nvim/    → ~/.config/nvim/
dotfiles/darwin/macos/.config/foo     → ~/.config/foo (macOS only)
```

## Adding Scripts

```bash
# Hoover an existing script (auto-detected from ~/bin path)
dotfiles add ~/bin/myscript

# Platform-specific
dotfiles add ~/bin/macos-only --darwin

# Explicit type
dotfiles add script ~/some/script
```

Or manually place scripts in `scripts/common/` (or `darwin/`/`linux/`).

## Package Mappings

When package names differ across managers, add to `packages/mappings.txt`:

```
# generic_name:brew_name:apt_name:pacman_name
fd:fd:fd-find:fd
```

Use `-` if a package isn't available for a manager.

## Commands

| Command | Description |
|---------|-------------|
| `install` | Install packages + stow dotfiles + link scripts + self-link |
| `uninstall` | Reverse of install |
| `packages [uninstall]` | Just packages |
| `dotfiles [uninstall]` | Just dotfiles |
| `scripts [uninstall]` | Just scripts |
| `add <path>` | Copy into repo (auto-detects config vs script) |
| `add config <path>` | Explicitly copy as config |
| `add script <path>` | Explicitly copy as script |
| `save [msg]` | Git add + commit |
| `push` | Git push |
| `sync [msg]` | Save + push |
| `status` | Show what's installed/linked |

## Conflict Handling

When a file already exists at the target location, you'll be prompted:

- **[o] Overwrite** - Backup existing to `~/.dotfiles-backup/` and replace
- **[s] Skip** - Leave existing file alone
- **[d] Diff** - Show differences between existing and repo version
- **[q] Quit** - Stop installation

## Requirements

- GNU Stow (`brew install stow` / `apt install stow` / `pacman -S stow`)
- Git
