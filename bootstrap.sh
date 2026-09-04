#!/bin/sh
# Bootstrap a machine from nothing to a working environment.
#
#   sh -c "$(curl -fsSL https://raw.githubusercontent.com/highb/dotfiles/main/bootstrap.sh)"
#
# Idempotent: every step checks before acting, so re-running it is a no-op and
# a half-finished run can simply be repeated.
#
# It will not install system packages behind your back. If a prerequisite is
# missing it tells you the command to run and stops.

set -eu

GITHUB_USER=highb
info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m  !!\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31merror\033[0m %s\n' "$*" >&2; exit 1; }
have()  { command -v "$1" >/dev/null 2>&1; }

# --- 0. prerequisites ------------------------------------------------------
# curl and git only. Everything else is installed by the tools below.
missing=""
for c in curl git; do have "$c" || missing="$missing $c"; done
if [ -n "$missing" ]; then
    if   have apt-get; then hint="sudo apt-get install -y$missing"
    elif have dnf;     then hint="sudo dnf install -y$missing"
    elif have pacman;  then hint="sudo pacman -S --needed$missing"
    elif have brew;    then hint="brew install$missing"
    else                    hint="install:$missing"
    fi
    die "missing prerequisites. Run:
  $hint"
fi
ok "curl and git present"

# --- 1. mise ---------------------------------------------------------------
# The one bootstrap that still matters: everything else comes from it.
if have mise; then
    ok "mise present ($(mise --version 2>/dev/null | head -1))"
else
    info "installing mise"
    curl -fsSL https://mise.run | sh
fi
MISE="${MISE:-$HOME/.local/bin/mise}"
have mise || [ -x "$MISE" ] || die "mise did not install to $MISE"
have mise && MISE=$(command -v mise)

# Put mise-managed tools on PATH for the rest of this script. Deliberately not
# `eval "$(mise activate ...)"`: that emits shell-function syntax which dash,
# the /bin/sh this runs under on Debian and Ubuntu, cannot parse. The shims
# directory is enough here and is shell-agnostic.
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"

# --- 2. chezmoi ------------------------------------------------------------
# From mise, deliberately. A snap or a stale binary in ~/bin will shadow it -
# see KNOWN_ISSUES.md, where exactly that had happened.
if "$MISE" which chezmoi >/dev/null 2>&1; then
    ok "chezmoi present via mise"
else
    info "installing chezmoi via mise"
    "$MISE" use --global chezmoi@latest
fi
CHEZMOI=$("$MISE" which chezmoi 2>/dev/null || command -v chezmoi)
[ -n "$CHEZMOI" ] || die "chezmoi unavailable after install"

# --- 3. dotfiles -----------------------------------------------------------
SRC=$("$CHEZMOI" source-path 2>/dev/null || echo "")
if [ -n "$SRC" ] && [ -d "$SRC" ]; then
    ok "dotfiles already checked out at $SRC"
    info "applying"
    "$CHEZMOI" apply
else
    info "initialising dotfiles from $GITHUB_USER"
    "$CHEZMOI" init --apply "$GITHUB_USER"
fi

# --- 4. rust, for metapac only --------------------------------------------
# metapac publishes no release binaries, so it cannot come from mise or
# cargo-binstall and must be compiled. This is the only reason rust is on the
# bootstrap path; if upstream ever ships binaries, steps 4 and 5 collapse into
# `mise use --global github:ripytide/metapac`.
if have cargo; then
    ok "cargo present"
else
    info "installing rust via mise (needed to build metapac)"
    "$MISE" use --global rust@latest
    "$MISE" reshim >/dev/null 2>&1 || true
fi
have cargo || die "cargo unavailable; cannot build metapac"

# --- 5. metapac ------------------------------------------------------------
if have metapac; then
    ok "metapac present ($(metapac --version 2>/dev/null | head -1))"
else
    info "building metapac (this takes a few minutes)"
    cargo install metapac --locked
fi

# --- 6. packages -----------------------------------------------------------
# Not run automatically. metapac sync has no dry-run and installs system
# packages under sudo; that is a decision, not a bootstrap step.
info "bootstrap complete"
cat <<'NEXT'

  Next, review and install the declared packages:

      metapac --config-dir "${XDG_CONFIG_HOME:-$HOME/.config}/metapac" sync
                            # shows the plan and asks before installing
      pkg-doctor            # duplicates, unowned binaries, what is missing

  Then open a new shell so the mise activation in ~/.config/shell takes effect.
NEXT
