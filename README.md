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
  private_dot_config/shell/ the shared shell layer (see its README)
  private_dot_config/       ghostty, git, metapac, nvim, starship
  bin/                      personal scripts
  private_README.md         becomes ~/README.md (0600)
```

## Shell configuration

Aliases, environment variables, `PATH` entries and tool integrations are
declared once in `home/.chezmoidata/shell.yaml` and rendered into
`~/.config/shell/*.sh` by templates. bash and zsh source the same generated
files and differ only in a single shell-specific fragment each.

Adding an alias is one line of YAML. Adding a POSIX shell is an rc file that
copies `dot_bashrc` with one word changed. Adding a non-POSIX shell such as
fish or nushell is one template that reads the same YAML — there is a worked
fish example in `home/private_dot_config/shell/README.md`.

## Installing on a new machine

To provision only selected tasks, first create
`${XDG_CONFIG_HOME:-$HOME/.config}/chezmoi/chezmoi.json` with the
`data.machine.packageGroups` setting shown in [Select packages by task](#select-packages-by-task).
Without that setting, bootstrap uses all groups.

```sh
DOTFILES_INSTALL_PACKAGES=1 sh -c "$(curl -fsSL https://raw.githubusercontent.com/highb/dotfiles/main/bootstrap.sh)"
```

The flag explicitly authorizes bootstrap prerequisites and selected task
packages. Without it, bootstrap exits before installing or applying anything.

`bootstrap.sh` is idempotent — re-running it is a no-op, and an interrupted run
can just be repeated. It will not install system packages behind your back: if
`curl` or `git` is missing it prints the command for your platform and stops.

What it does, and why in that order:

1. **mise**, from `https://mise.run`. The one bootstrap that still matters.
2. **chezmoi, via mise.** Deliberately not a snap and not a loose binary in
   `~/bin` — both had happened here, and the `~/bin` copy was shadowing
   everything else with a build from March 2024.
3. **`chezmoi init --apply`**, which lays down the dotfiles, generates
   `~/.config/metapac/` for the selected groups, and runs the package hooks
   unless `machine.manualProvisioning` disables them. The bootstrap opt-in is
   inherited by both hooks, so selected task packages may be installed here.
4. **rust, via mise** — needed only to build metapac.
5. **`cargo install metapac --locked`.**
6. Stops with instructions to review the declarations, run a normal
   `chezmoi apply`, then `DOTFILES_INSTALL_PACKAGES=1 chezmoi apply`.
   This also retries hooks skipped before their prerequisites were installed.
   metapac uses the generated XDG config explicitly, including on macOS.
   On macOS a chezmoi-managed symlink also points metapac's native config
   directory, `~/Library/Application Support/metapac`, at that XDG one, so a
   bare `metapac` command finds the inventory instead of silently reporting an
   empty one. Scripts keep passing `--config-dir` so they stay portable.

Steps 4 and 5 exist for one package. metapac publishes no release binaries, so
it cannot come from mise or `cargo-binstall` and has to be compiled. Most other
selected tools arrive through metapac; `mise-direct` tools use the earlier hook.
If upstream ever ships binaries, both steps collapse into a single
`mise use --global`.

`metapac sync` has no dry-run and can install system packages under sudo.
Neither hook runs an installer during ordinary `chezmoi apply` or
`chezmoi update`, even with a terminal. `DOTFILES_INSTALL_PACKAGES=1` is the
only hook opt-in; it authorizes metapac's `--no-confirm` mode as well as mise.

### Arch or Fedora

The same one-liner works — `bootstrap.sh` detects the package manager for its
prerequisite check. Note that the inventory itself is still Ubuntu- and
macOS-shaped: `arch:` and `dnf:` names are missing for most tools, so a lot will
report as UNRESOLVED until they are filled in.

### Existing macOS machines

Review `chezmoi diff` before applying: bootstrap is for provisioning, not for
preserving an existing laptop's package ownership. Local template data belongs
under `data.machine` in the chezmoi configuration, outside this repository:

- `packageGroups` selects packages and matching config bundles; see
  [Select packages by task](#select-packages-by-task).
- `gitSigningKey` and `gitAllowedSignersFile` keep machine-specific signing
  settings. macOS uses the 1Password app signer and existing credential helpers.
- `packageProviders` maps logical tool names to explicit backends, overriding
  inventory preferences. An unavailable override is reported, not silently
  replaced by another provider.
- `packageExcludes` lists tools intentionally managed outside metapac.
- `manualProvisioning: true` excludes both package-install scripts from chezmoi
  operations, even with the install opt-in flag. Packages must then be installed
  through explicit package-manager commands; bootstrap prerequisites are separate.

The private source attributes preserve `0700` on `.config`, `.config/git`,
`.local`, `.local/share`, `Applications`, `Documents`, `Templates`, `sandbox`,
`scripts`, `src`, `svc`, and `tools`. `~/README.md` is private with mode `0600`.
The `sandbox`, `scripts`, `svc`, and `tools` entries manage only directories,
not their contents. Shell history and local shell overrides are excluded from
management.

### Select packages by task

Run `chezmoi edit-config` and set `data.machine.packageGroups`. For example,
in a JSON configuration, merge this field into the existing `machine` object
without replacing provider overrides, exclusions, or other settings:

```json
{
  "data": {
    "machine": {
      "packageGroups": ["core", "shell", "development", "kubernetes"]
    }
  }
}
```

For TOML, add `packageGroups = ["core", "shell"]` under `[data.machine]`.

| Group | Packages |
| --- | --- |
| `core` | age, chezmoi, curl, file, git, jq, magic-wormhole, metapac, pre-commit, procps, pwgen, ripgrep, trufflehog, yq |
| `shell` | atuin, bat, direnv, eza, fd, fzf, navi, starship, zoxide |
| `development` | build-essential, direnv, exercism, gh, git, httpie, kickstart, node, pre-commit, ruby, rust, trufflehog, vale, vim, xh |
| `cloud` | awscli, google-cloud-cli |
| `kubernetes` | helm, k3d, kubectl, kubie, kustomize |
| `writing` | hugo, markdownlint-cli, node, prettier, vale, zola |
| `desktop` | 1password, code, discord, ghostty, slack |
| `ai` | oh-my-pi |

Groups combine without duplicate installs. No group is mandatory; include `core`
explicitly if wanted. Required runtimes are listed alongside their tools:
`writing`, for example, includes Node for its npm tools. `packageExcludes` wins
over group membership, and `packageProviders` still chooses the package manager.
Selected packages without an available provider remain marked `UNRESOLVED`.

- **Field omitted:** all defined groups, subject to platform-specific file rules.
- **Empty list (`[]`):** no task packages or task config bundles; package-control
  files and general organizational resources remain managed.
- **Unknown group or malformed selection:** rendering fails rather than silently
  selecting something else.

Use an explicit list to avoid opting into groups added to the repository later.
Group membership is defined in `home/.chezmoidata/packages.yaml`; adding a
package to a selected group requests it on the next explicitly opted-in apply.

Preview and write the generated package manifests without running install hooks:

```sh
chezmoi diff ~/.config/metapac
chezmoi apply --include=files,dirs ~/.config/metapac
```

When ready to authorize installation through the hooks:

```sh
DOTFILES_INSTALL_PACKAGES=1 chezmoi apply
```

Do not export this flag in shell startup files: keep consent scoped to one
command. A skipped normal apply followed by an opted-in apply runs the hooks
without needing another inventory edit. An unchanged repeated opted-in apply
retains chezmoi's normal run-on-change behavior.

With `machine.manualProvisioning: true`, neither hook runs, even with this flag.
Keep that hard stop and install selected tools manually, or set it to `false`
to use the explicit opt-in workflow. For manual provisioning, install selected
`mise-direct` tools explicitly, then run
`metapac --config-dir "${XDG_CONFIG_HOME:-$HOME/.config}/metapac" sync`.
The direct tools are `npm:markdownlint-cli` and `npm:prettier` in `writing`,
and `github:can1357/oh-my-pi` in `ai`; exclusions still apply.

Deselecting a group stops requesting its packages; it does **not** uninstall
them or remove existing mise settings. Do not use `metapac clean` as part of
group selection. With installation consent, `bootstrap.sh` still installs its
prerequisites (mise, chezmoi, Rust/cargo, and metapac), even with an empty task
selection. This consent policy governs provisioning, not Neovim's own plugin,
language-server, or parser installation when you launch the editor.

### Task and platform deployment

The same `packageGroups` selection controls file bundles through
`home/.chezmoiignore`. Package exclusions and provider overrides do not suppress
configs, so an externally installed tool can still use its managed config.

| Selected task | Managed bundle |
| --- | --- |
| `shell` | bash/zsh startup files, the complete shared shell layer, Starship |
| `core` or `development` | Git configuration and allowed signers |
| `development` | Neovim and repository helper scripts |
| `development` or `writing` | Scaffold command and all scaffold templates |
| `development` or `writing` | Vale contexts, vocabularies, and `vale-as` |
| `desktop` | Ghostty configuration |
| `desktop`, on Linux only | PulseAudio and GNOME helper scripts |

Cloud, Kubernetes, and AI currently have no separate managed config bundles.
Package manifests, `pkg-doctor`, general documentation, and organizational
directories remain available regardless of task selection.

For a headless host, `["core", "shell"]` omits editor, scaffold, and desktop
bundles; add `development` for Neovim and project tooling. The PulseAudio/GNOME
helpers are not deployed on macOS. Git signing identity and signer availability
remain machine-specific prerequisites; task selection does not disable signing.

Preview file selection with `chezmoi managed` and changes with `chezmoi diff`,
then use ordinary `chezmoi apply` to deploy without authorizing installations.
**Ignoring is not deletion:** existing files from deselected groups remain on
disk and may still be active. No automatic removal is performed. Local shell
overrides, histories, and Neovim repository metadata remain excluded.

### Prose linting

[Vale](https://vale.sh) is configured per writing context rather than once.
`~/.config/vale/.vale.ini` is the user-level file, which Vale reads underneath
whatever configuration a run already found, so it holds only what should hold
everywhere: the styles to download, the vocabularies, and a spell check. The
opinionated parts live in one file per context:

| Context | For | Level |
| --- | --- | --- |
| `docs` | Design docs, RFCs, runbooks, READMEs, tickets | warning |
| `blog` | Posts and essays with a public byline | suggestion |
| `prose` | Fiction and creative writing | warning |
| `jobs` | Job posts and hiring copy | suggestion |

```sh
vale-as docs README.md              # one context, then vale's own arguments
vale-as blog --minAlertLevel=error post.md
vale-as --list
```

`vale-as` sets `VALE_CONFIG_PATH` and execs `vale`, so every vale flag still
works. `vale ls-config` prints what a directory actually resolves to, and
`vale --no-global` leaves the user-level file out of a run.

Contexts do not inherit from each other, because Vale has no include: each one
is a whole configuration, read on top of the user-level file. Two things about
that layering decide how these files are written. List keys such as
`BasedOnStyles` **join** across files, so a style named in the user-level file
is added to every project and no context can remove it — which is why `[*]`
there names only the built-in `Vale` style. Single-value keys such as
`MinAlertLevel` are taken from the file read last, so a context, or a project,
overrides the default.

Each context is tuned rather than switched on. Of the nine installed styles,
three check passive voice and three check clichés, so one of each runs and the
rest are off; one readability metric runs of the seven the `Readability` style
installs. The rules switched off in `docs.ini` were measured against this
repository's own documentation, and each is a false positive in technical prose
rather than a matter of taste. `prose.ini` leaves `Std`, `write-good`, `alex`
and `neighbor` out entirely: everything they check is a choice in fiction.

Styles are separate downloads. `Packages` in the user-level file names them and
`vale sync` fetches them into `~/.local/share/vale/styles`, which
`run_onchange_after_25-vale-sync.sh` does under the same
`DOTFILES_INSTALL_PACKAGES=1` consent as every other installer here.

Spelling needs a vocabulary, or Vale reports the whole toolchain. Two of them
live under the StylesPath:

- `Inventory` is rendered from `packages.yaml`, so every tool is named once and
  spelled everywhere. It covers the logical name, the name each package manager
  knows it by, and the package managers themselves. Do not edit it.
- `Local` is hand-maintained, for general technical English that Vale's
  dictionary lacks.

Both are published. **Employer terminology, internal document names and house
rules do not belong in either.** For those, two paths are kept out of the
repository by `.chezmoiignore`, and a `chezmoi add` of them does nothing:

```sh
# A context that cannot be published. A local file wins over a published one
# of the same name, so `vale-as work` finds this and `vale-as docs` is intact.
cp ~/.config/vale/contexts/docs.ini ~/.config/vale/contexts/work.local.ini

# Terminology to accept. Add `Vocab = Work` to that context; list keys join,
# so it is added to Inventory and Local rather than replacing them.
mkdir -p ~/.local/share/vale/styles/config/vocabularies/Work
$EDITOR ~/.local/share/vale/styles/config/vocabularies/Work/accept.txt
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

- `home/private_dot_config/nvim` — started from
  [kickstart.nvim](https://github.com/nvim-lua/kickstart.nvim) and since
  diverged. Fully owned here, not tracked upstream.

## Provisioning

chezmoi manages file content; it has no package model. Packages are handled by
[metapac](https://github.com/ripytide/metapac), with chezmoi supplying the one
thing metapac lacks — resolving a single logical inventory to one backend per
tool, per machine.

```
home/.chezmoidata/packages.yaml   tool definitions and task groups
        |
        |  machine.packageGroups union, minus packageExcludes
        |  packageProviders override, then prefer ++ platform priority
        |  skipping backends this machine does not have (lookPath)
        v
~/.config/metapac/{config,groups/dotfiles}.toml    generated - do not edit
        |
        v
metapac sync                                       execution
```

- `home/.chezmoidata/packages.yaml` — every tool declared once, with the name
  it goes by in each backend. Backend ids are metapac's own, so Arch is `arch`.
- `home/private_dot_config/metapac/**.tmpl` — the resolution layer.
- `home/.chezmoitemplates/package-{selection,resolution}` — shared task
  selection and provider resolution for manifests, deployment rules, and hooks.
- `home/.chezmoitemplates/metapac-{platform,backends}` — platform and backend
  detection.
- `home/run_onchange_after_20-metapac-sync.sh.tmpl` — hashes the parsed
  inventory, machine package policy, and per-command install consent. Neither
  it nor the direct mise hook installs without `DOTFILES_INSTALL_PACKAGES=1`.
- `home/run_after_30-pre-commit.sh.tmpl` — activates the repository's Git hook
  after provisioning when pre-commit is available. It installs no packages and
  is not disabled by `manualProvisioning`.
- `docs/provisioning-gap.md` — why this shape.

- `KNOWN_ISSUES.md` — upstream bugs, tool limitations, and the gotchas that
  will catch you. Read it before debugging something that looks impossible.

Remaining gaps, and what is left of the tool that was going to be written, are
in `TODO.md` in [.bhell](https://github.com/highb/.bhell).

### Commit protection

`pre-commit` and TruffleHog are managed tools in both `core` and `development`,
not one-off bootstrap downloads. Homebrew supplies them on this laptop;
`packageProviders` can select other declared backends. The hook requires
pre-commit 4.4+ and a TruffleHog version supporting `--fail-on-scan-errors`.

After those tools are available, `chezmoi apply` activates the hook in this
repository. You can also run this directly from its working tree:

```sh
pre-commit install
pre-commit run --all-files
```

Git does not transfer hooks when cloning. A fresh checkout is not protected
until hook installation succeeds; apply prints a warning if pre-commit is
missing. An installed hook blocks commits if TruffleHog is missing or fails.

The gate exports regular-file **raw index blobs** to a private temporary
directory, so it scans what will be committed, not unstaged edits or files
outside the repository. Symlinks and submodules are not followed. TruffleHog
runs offline, without credential verification or update checks, and blocks
unverified findings too. Scanner output is suppressed because even errors can
contain credential values; inspect flagged staged changes privately.

This is detection, not proof that arbitrary secret text is safe. Keep secrets
out of tracked files, and do not bypass the hook to commit a finding.

### Deployment and provisioning checks

Requires Python 3.11+, chezmoi, pre-commit, TruffleHog, `/bin/bash`, and zsh:

```sh
python3 -B -m unittest discover -s tests -v
```

The checks render and apply real templates in temporary homes, exercise
provisioning with fake package managers, and start bash/zsh with isolated
environment, history, and local overrides. Secret-gate tests use synthetic
markers and offline scanning in disposable Git repositories. No test reads
workstation credentials or installs dotfile-managed packages.

`.github/workflows/checks.yml` runs the secret gate and test suite on Ubuntu
24.04 and macOS 15. Actions are pinned by commit; chezmoi and TruffleHog release
binaries are pinned and SHA256-checked. Runner setup supplies Python, pre-commit,
and Ubuntu zsh as test prerequisites. Jobs use read-only repository permissions
and do not persist checkout credentials or receive repository secrets.

## TODO

- `metapac --config-dir "${XDG_CONFIG_HOME:-$HOME/.config}/metapac" sync`
  to install the tools `shell.yaml` assumes: `fd`, `bat`, `eza`,
  `zoxide` (`atuin` is still unresolvable — brew only, and there is no brew here)
- Run `pkg-doctor`: 4 duplicate installs, 13 unowned binaries, 17 declared
  tools not yet installed
- Fill in `arch:` and `dnf:` names, when a machine of either kind exists
- Manage application colour schemes coherently
- Secrets via a real backend rather than by leaving them out
- Move `.tmux.conf.local` and the flavours config out of `.bhell` and into here
