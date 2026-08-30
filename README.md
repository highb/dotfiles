# dotfiles

Personal configuration, managed with [chezmoi](https://www.chezmoi.io).

## Layout

`.chezmoiroot` points chezmoi at `home/`, so the top level of this repository
is repository documentation and everything under `home/` is a thing that lands
in `$HOME`.

```
.chezmoiroot              -> "home"
home/
  .chezmoidata/shell.yaml   single source of truth for shell config
  .chezmoiignore
  dot_bashrc                thin, sources ~/.config/shell
  dot_zshrc                 thin, sources ~/.config/shell
  dot_profile               login shells: environment only
  dot_zshenv                every zsh: environment only
  dot_config/shell/         the shared shell layer (see its README)
  dot_config/               ghostty, mise, nvim
  bin/                      personal scripts
  README.md                 becomes ~/README.md
```

## Shell configuration

Aliases, environment variables, `PATH` entries and tool integrations are
declared once in `home/.chezmoidata/shell.yaml` and rendered into
`~/.config/shell/*.sh` by templates. bash and zsh source the same generated
files and differ only in a single shell-specific fragment each.

Adding an alias is one line of YAML. Adding a POSIX shell is an rc file that
copies `dot_bashrc` with one word changed. Adding a non-POSIX shell such as
fish or nushell is one template that reads the same YAML — there is a worked
fish example in `home/dot_config/shell/README.md`.

## Installing on a new machine

Both paths install [mise](https://mise.jdx.dev) first and let it manage
chezmoi, so the two stay on known versions.

### Ubuntu / Debian

```sh
sudo apt install -y curl git
curl https://mise.run | sh
eval "$(~/.local/bin/mise activate bash)"
mise use --global chezmoi@latest
chezmoi init --apply highb
exec "$SHELL" -l
```

### Arch / Manjaro

```sh
pamac install mise
mise use --global chezmoi@latest
chezmoi init --apply highb
exec "$SHELL" -l
```

### Verifying the download

```sh
gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys 0x7413A06D
curl https://mise.jdx.dev/install.sh.sig | gpg --decrypt > install.sh
# confirm the signature is mise's release key before running
sh ./install.sh
```

## Day to day

```sh
chezmoi cd            # into this repository
chezmoi edit --apply  # edit a managed file and apply it in one step   (alias: cme)
chezmoi diff          # what would change
chezmoi apply         # change it
chezmoi update        # pull, then apply
dotpush "message"     # add, commit and push this repository
```

Dotfiles are **not** synced automatically on shell startup. That used to run on
every interactive bash shell, which made every new terminal wait on the
network; `chezmoi update` is now something you run deliberately.

## Vendored code

- `home/dot_config/nvim` — started from
  [kickstart.nvim](https://github.com/nvim-lua/kickstart.nvim) and since
  diverged. Fully owned here, not tracked upstream.

## Provisioning

chezmoi manages file content; it has no package model. Packages are handled by
[metapac](https://github.com/ripytide/metapac), with chezmoi supplying the one
thing metapac lacks — resolving a single logical inventory to one backend per
tool, per machine.

```
home/.chezmoidata/packages.yaml   single source of truth: 45 tools
        |
        |  chezmoi template: prefer ++ platform priority, skipping
        |  backends this machine does not have (lookPath)
        v
~/.config/metapac/{config,groups/dotfiles}.toml    generated - do not edit
        |
        v
metapac sync                                       execution
```

- `home/.chezmoidata/packages.yaml` — every tool declared once, with the name
  it goes by in each backend. Backend ids are metapac's own, so Arch is `arch`.
- `home/dot_config/metapac/**.tmpl` — the resolution layer.
- `home/.chezmoitemplates/metapac-{platform,backends}` — shared partials, so
  the config and group templates cannot disagree about the platform.
- `home/run_onchange_after_20-metapac-sync.sh.tmpl` — hashes the parsed
  inventory and runs `metapac sync` when it changes. Only with a terminal to
  confirm at; `METAPAC_AUTOSYNC=1` opts into unattended installs.
- `docs/provisioning-gap.md` — why this shape.

Remaining gaps, and what is left of the tool that was going to be written, are
in `TODO.md` in [.bhell](https://github.com/highb/.bhell).

## TODO

- `metapac sync` to install the tools `shell.yaml` assumes: `fd`, `bat`, `eza`,
  `zoxide` (`atuin` is still unresolvable — brew only, and there is no brew here)
- Resolve two live duplicate installs: `ripgrep` (mise + apt) and `1password`
  (snap + apt)
- Fill in `arch:` and `dnf:` names, when a machine of either kind exists
- Manage application colour schemes coherently
- Secrets via a real backend rather than by leaving them out
- Move `.tmux.conf.local` and the flavours config out of `.bhell` and into here
