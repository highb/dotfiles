# ~/.config/shell/interactive.sh - shared interactive setup that is real logic
# rather than data, and so does not belong in shell.yaml.

if [ "${DOTFILES_SKIP_LOCAL_INTEGRATIONS:-0}" = "1" ]; then
    return 0
fi

# Colourise ls and friends.
if command -v dircolors >/dev/null 2>&1; then
    if [ -r "${HOME}/.dircolors" ]; then
        eval "$(dircolors -b "${HOME}/.dircolors")"
    else
        eval "$(dircolors -b)"
    fi
fi

# Tell gpg and 1Password's ssh signer which terminal to prompt on.
if command -v tty >/dev/null 2>&1 && tty -s; then
    GPG_TTY="$(tty)"
    export GPG_TTY
fi
