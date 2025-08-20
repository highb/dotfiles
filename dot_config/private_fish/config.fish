if status is-interactive
    # Commands to run in interactive sessions can go here
end

function fish_greeting
    echo "🐟 Something fishy this way comes"
end

mise activate fish | source
