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

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/highb/dotfiles/main/bootstrap.sh)"
```

`bootstrap.sh` is idempotent — re-running it is a no-op, and an interrupted run
can just be repeated. It will not install system packages behind your back: if
`curl` or `git` is missing it prints the command for your platform and stops.

What it does, and why in that order:

1. **mise**, from `https://mise.run`. The one bootstrap that still matters.
2. **chezmoi, via mise.** Deliberately not a snap and not a loose binary in
   `~/bin` — both had happened here, and the `~/bin` copy was shadowing
   everything else with a build from March 2024.
3. **`chezmoi init --apply`**, which lays down the dotfiles and generates
   `~/.config/metapac/` from the inventory.
4. **rust, via mise** — needed only to build metapac.
5. **`cargo install metapac --locked`.**
6. Stops, and tells you to run `metapac sync` yourself.

Steps 4 and 5 exist for one package. metapac publishes no release binaries, so
it cannot come from mise or `cargo-binstall` and has to be compiled; everything
else in the inventory arrives through metapac afterwards. If upstream ever ships
binaries, both steps collapse into a single `mise use --global`.

The last step is not automatic on purpose. `metapac sync` has no dry-run and
installs system packages under sudo, which is a decision rather than a bootstrap
step. `METAPAC_AUTOSYNC=1` opts into running it from the chezmoi hook.

### Arch or Fedora

The same one-liner works — `bootstrap.sh` detects the package manager for its
prerequisite check. Note that the inventory itself is still Ubuntu- and
macOS-shaped: `arch:` and `dnf:` names are missing for most tools, so a lot will
report as UNRESOLVED until they are filled in.

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

- `KNOWN_ISSUES.md` — upstream bugs, tool limitations, and the gotchas that
  will catch you. Read it before debugging something that looks impossible.

Remaining gaps, and what is left of the tool that was going to be written, are
in `TODO.md` in [.bhell](https://github.com/highb/.bhell).

## TODO

- `metapac sync` to install the tools `shell.yaml` assumes: `fd`, `bat`, `eza`,
  `zoxide` (`atuin` is still unresolvable — brew only, and there is no brew here)
- Run `pkg-doctor`: 4 duplicate installs, 13 unowned binaries, 17 declared
  tools not yet installed
- Fill in `arch:` and `dnf:` names, when a machine of either kind exists
- Manage application colour schemes coherently
- Secrets via a real backend rather than by leaving them out
- Move `.tmux.conf.local` and the flavours config out of `.bhell` and into here
