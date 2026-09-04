# ~/.config/shell/functions.sh - functions shared by every POSIX shell.
#
# Hand-written, unlike its generated neighbours: functions are prose, not data.

# mkdir -p a directory and cd into it.
mkcd() {
    [ "$#" -eq 1 ] || { echo "usage: mkcd DIR" >&2; return 2; }
    mkdir -p -- "$1" && cd -- "$1"
}

# Print PATH one entry per line, in search order.
path() {
    printf '%s\n' "${PATH}" | tr ':' '\n'
}

# Stage, commit and push everything in the chezmoi source repo.
dotpush() {
    chezmoi git -- add -A || return
    if [ -n "${1-}" ]; then
        chezmoi git -- commit -m "$1" || return
    else
        chezmoi git -- commit || return
    fi
    chezmoi git -- push
}
