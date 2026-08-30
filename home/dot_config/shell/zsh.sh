# ~/.config/shell/zsh.sh - zsh-only interactive settings.
#
# Anything portable belongs in the shared files next door. This holds only the
# parts with no bash equivalent, and mirrors bash.sh choice for choice.

# History: large, deduplicated, shared live between concurrent shells.
# The filename is .zsh_histfile rather than the more usual .zsh_history
# because that is where this machine's history already lives.
HISTFILE="${HOME}/.zsh_histfile"
HISTSIZE=1000000
SAVEHIST=1000000
setopt append_history share_history
setopt hist_ignore_all_dups hist_ignore_space hist_reduce_blanks

setopt autocd extendedglob nomatch
unsetopt beep notify

# Completion.
zstyle ':completion:*' completer _expand _complete _ignored
zstyle ':completion:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}'
zstyle ':completion:*' menu select
autoload -Uz compinit && compinit

bindkey -v              # vi keybindings, matching bash's `set -o vi`

# Up/Down search history for whatever has already been typed on the line.
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey '^[[A' up-line-or-beginning-search
bindkey '^[[B' down-line-or-beginning-search

# Fallback prompt, used only when starship is not installed - tools.sh loads
# after this file and overrides the prompt when it is.
autoload -Uz promptinit && promptinit
prompt walters
