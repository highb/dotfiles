#!/usr/bin/env sh

# This script toggles dark mode off and on. I've associated it with the keyboard shortcut
# Super+Shift+D using a Custom Shortcut.

# Reminder: You can create a custom keyboard shortcut for the script in the Settings app (under Keyboard → View and Customize Shortcuts → Custom Shortcuts)
# TODO: Can this be scripted, as well?

## Sources

# [Answer by Sean Hammond on StackOverflow](https://askubuntu.com/questions/1406616/how-can-i-toggle-between-dark-mode-and-light-mode-on-the-command-line)

set -euo

# You can use the gsettings command in a terminal to change the value of the org.gnome.desktop.interface color-scheme setting to either prefer-dark or prefer-light
# For legacy apps (for example: GNOME Terminal) you also need to set the org.gnome.desktop.interface gtk-theme setting to either 'Adwaita-dark' or 'Adwaita'
if test "$(gsettings get org.gnome.desktop.interface color-scheme)" = "'prefer-light'"; then
  gsettings set org.gnome.desktop.interface color-scheme prefer-dark
  gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
else
  gsettings set org.gnome.desktop.interface color-scheme prefer-light
  gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'
fi
