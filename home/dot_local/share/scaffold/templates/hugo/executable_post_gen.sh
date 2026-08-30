#!/bin/sh
# Runs after generation. A freshly written mise.toml is untrusted, and mise
# silently ignores an untrusted config - so trust it here rather than leaving
# the user to discover that their tools never activated.
set -eu
command -v mise >/dev/null 2>&1 || exit 0
mise trust --yes >/dev/null 2>&1 || mise trust >/dev/null 2>&1 || true
echo "mise config trusted. Next: mise install"
