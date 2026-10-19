#!/usr/bin/env bash
# Editor-free host configuration. Run from any directory after chezmoi init.
set -euo pipefail
CHEZMOI=${CHEZMOI:-chezmoi}
[[ -t 0 ]] || { echo 'The configuration wizard requires a terminal.' >&2; exit 1; }
config=$("$CHEZMOI" --color=false --no-tty execute-template '{{ .chezmoi.configFile }}')
# Keep the existing format and all unrelated configuration, including overrides.
case "$config" in *.json|*.toml|*.yaml|*.yml) ;; *) echo "Unsupported config format: $config" >&2; exit 1;; esac
roles=$("$CHEZMOI" --color=false --no-tty execute-template '{{ $s := includeTemplate "package-selection" . | fromJson }}{{ range $g, $members := .packages.groups }}{{ $g }}|{{ if has $g $s.groups }}y{{ else }}n{{ end }}|{{ join ", " $members }}{{ "\n" }}{{ end }}')
selected=()
while IFS='|' read -r group current members; do
    printf '\n%s: %s\nEnable this role? [%s] ' "$group" "$members" "$current" > /dev/tty
    read -r answer < /dev/tty
    answer=${answer:-$current}
    case "$answer" in y|Y|yes) selected+=("\"$group\"");; n|N|no) ;; *) echo 'Please rerun and answer y or n.' >&2; exit 1;; esac
done <<< "$roles"
export DOTFILES_WIZARD_GROUPS="[$(IFS=,; echo "${selected[*]-}")]"
export DOTFILES_WIZARD_CONFIG="$config"
mkdir -p "$(dirname "$config")"
umask 077
tmp=$(mktemp "$config.XXXXXX")
trap 'rm -f "$tmp"' EXIT
"$CHEZMOI" --color=false --no-tty execute-template '{{ $path := env "DOTFILES_WIZARD_CONFIG" }}{{ $c := dict }}{{ if stat $path }}{{ $raw := include $path }}{{ if hasSuffix ".json" $path }}{{ $c = fromJson $raw }}{{ else if hasSuffix ".toml" $path }}{{ $c = fromToml $raw }}{{ else }}{{ $c = fromYaml $raw }}{{ end }}{{ end }}{{ $data := get $c "data" | default dict }}{{ $machine := get $data "machine" | default dict }}{{ $_ := set $machine "packageGroups" (env "DOTFILES_WIZARD_GROUPS" | fromJson) }}{{ $_ := set $data "machine" $machine }}{{ $_ := set $c "data" $data }}{{ if hasSuffix ".json" $path }}{{ $c | toPrettyJson }}{{ else if hasSuffix ".toml" $path }}{{ $c | toToml }}{{ else }}{{ $c | toYaml }}{{ end }}' > "$tmp"
mv "$tmp" "$config"
echo "Saved host configuration to $config"
plan=$("$CHEZMOI" --color=false --no-tty execute-template '{{ includeTemplate "package-plan" . }}')
printf '%s\n' "$plan"
printf '\nApply dotfiles and install these packages? [y/N] '
read -r answer
case "$answer" in
    y|Y|yes) DOTFILES_INSTALL_PACKAGES=1 "$CHEZMOI" apply ;;
    *) echo 'Configuration saved; installation skipped.' ;;
esac
