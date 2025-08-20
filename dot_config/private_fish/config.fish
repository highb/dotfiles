if status is-interactive
    # Commands to run in interactive sessions can go here
end

function fish_greeting
    echo "🐟 Something fishy this way comes"
end

function chezmoi_edit
    chezmoi edit --apply $argv
end

function chezmoi_commit_push
    chezmoi git add .
    chezmoi git commit
    chezmoi git push
end

function chezmoi_todo_dotfiles
    chezmoi_edit TODO.dotfiles
    chezmoi_commit_push
end

mise activate fish | source

set -gx EDITOR nvim
