# ~/.config/shell/bash.sh - bash-only interactive settings.
#
# Anything portable belongs in the shared files next door. This holds only the
# parts with no zsh equivalent, and mirrors zsh.sh choice for choice.

# History: large, deduplicated, appended rather than clobbered.
HISTFILE="${HOME}/.bash_history"
HISTSIZE=1000000
HISTFILESIZE=1000000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend

shopt -s checkwinsize   # keep LINES/COLUMNS correct after every command
if [ "${BASH_VERSINFO[0]}" -ge 4 ]; then
    shopt -s globstar   # ** matches across directory boundaries (Bash 4+)
fi
shopt -s cdspell        # forgive small typos in cd arguments

set -o vi               # vi keybindings, matching zsh's `bindkey -v`

# Keep optional host integrations out of SSH and isolated shell startup.
if [ "${DOTFILES_SKIP_LOCAL_INTEGRATIONS:-0}" != "1" ]; then
    # Friendlier `less` for non-text input.
    [ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

    # Distro-provided completions.
    if ! shopt -oq posix; then
        if [ -r /usr/share/bash-completion/bash_completion ]; then
            . /usr/share/bash-completion/bash_completion
        elif [ -r /etc/bash_completion ]; then
            . /etc/bash_completion
        fi
    fi
fi

# Fallback prompt, used only when starship is not installed - tools.sh loads
# after this file and overrides PS1 when it is.
PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
