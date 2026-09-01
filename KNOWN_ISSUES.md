# Known issues

Things that are broken, missing, or surprising in this setup and the tools it
depends on. Everything here was reproduced on Ubuntu 24.04 with the versions
noted; nothing is inferred from documentation alone.

Fixed problems are not listed. Workarounds that are load-bearing are, because
removing one without understanding it will break something.

**Versions this was observed against:** metapac 0.10.1, kickstart 0.6.0,
chezmoi 2.47.1, mise 2026.6.14, nix 2.25.3, cargo 1.93.0.

---

## Upstream bugs

### metapac: one failing backend aborts the entire run

metapac's nix backend shells out to `nix profile list --json --no-pretty`
(`src/backends/nix.rs:73`). `--no-pretty` does not exist in older nix, so the
command fails — and metapac treats a single backend's error as fatal to the
whole invocation rather than skipping that backend.

```
$ metapac unmanaged
error: unrecognised flag '--no-pretty'
Error:
   0: command failed: "nix profile list --json --no-pretty", exit_status_code: 256
```

That killed `unmanaged` outright, including the apt, mise, snap and cargo
results that had nothing to do with nix.

**Which nix versions are affected:** the flag is **absent from 2.26.2** and
documented by **2.28**, so it arrived in 2.27 or 2.28. Upgrading to 2.26 is not
enough. This machine has 2.25.3.

**Workaround, and it is load-bearing:** `backend_probe` in `packages.yaml`. A
backend may declare a command that must succeed before it is used; nix declares
`nix profile list --json --no-pretty`. On a nix without the flag the probe fails
and nix drops out of resolution; on a newer nix it passes and nix takes its
place second in the priority order. Removing the probe re-breaks every metapac
command on this machine.

**What would fix it upstream:** a backend that cannot be queried should be a
warning that excludes that backend, not a fatal error.

### kickstart: `validate` resolves hook paths against the working directory

`kickstart validate` reports `Hook file 'post_gen.sh' was not found` for a
template whose hook is present and executable, unless you happen to be standing
in the template directory.

The two code paths disagree:

- `src/definition.rs:129-132` — validation does `Path::new(&hook).exists()`,
  which is relative to the process working directory.
- `src/generation.rs:179` — generation does `self.path.join(&hook.path)`,
  relative to the template.

So generation works and validation does not, which is the confusing way round.

**Workaround:** `cd` into the template directory and validate the manifest by
name.

```sh
(cd ~/.local/share/scaffold/templates/python-uv && kickstart validate template.toml)
```

**What would fix it upstream:** validation should join against the template
path, the way generation does. Two lines.

### kickstart: the `directory` field does not strip its own name

The manifest supports `directory = "template"`, documented as *"Templates with a
`directory` field will now no longer include that directory name in the
output."* On 0.6.0 it does include it: files land in `<output>/template/…`
rather than `<output>/…`.

**Workaround:** templates here are flat — the files sit next to `template.toml`
rather than inside a subdirectory, and `directory` is not used at all.

---

## Upstream limitations

Not bugs. Design gaps that shape how this repository is put together.

### metapac has no dry-run

`metapac sync` takes `--no-confirm` and nothing else. There is no `--dry-run`,
no `plan`, no machine-readable diff. You can see what it would do only by
running it and declining the prompt, which is not scriptable.

**Consequence:** the chezmoi hook
(`home/run_onchange_after_20-metapac-sync.sh.tmpl`) is TTY-gated. With a
terminal it runs `metapac sync` and lets you confirm; without one it reports and
exits 0. Unattended `sudo apt install` during a `chezmoi apply` on a new machine
is not an acceptable default. `METAPAC_AUTOSYNC=1` opts in.

### metapac rejects any mise name that is not in the registry

metapac's mise backend validates every package name against
`mise search --no-headers --quiet` (`src/backends/mise.rs:43`), which lists
**registry tools only**. A prefixed name — `npm:prettier`,
`github:can1357/oh-my-pi`, `aqua:sharkdp/bat` — is not in that list, fails
validation, and **aborts metapac's entire run**, taking every other backend
with it.

```
$ mise search 'github:Keats/kickstart'
mise ERROR tool github:Keats/kickstart not found in registry
```

This is easy to walk into: mise itself installs such names happily, so the
inventory looks correct and only metapac objects.

**Workaround:** `status: mise-direct` in the inventory. Those tools are excluded
from the generated metapac groups and installed by
`run_onchange_after_10-mise-direct.sh.tmpl` instead, which calls
`mise use --global` directly. `metapac unmanaged` reports them as undeclared,
which is correct rather than a defect.

Currently mise-direct: `markdownlint-cli`, `oh-my-pi`, `prettier`.

**Consequence for bootstrap:** it also rules out installing metapac itself via
mise's `github:` backend, which would otherwise take rust off the bootstrap
path. See below.

### metapac publishes no release binaries

Its latest release has zero assets and the repository has only `ci.yml`, no
release workflow. So metapac cannot be installed by mise's `github:` backend,
by `cargo-binstall`, or by any brew formula pointing at a prebuilt binary — it
must be compiled.

```
$ mise install 'ubi:ripytide/metapac@0.10.1'
mise ERROR could not find a release asset after filtering for valid extensions
```

**Consequence:** rust and cargo are on the bootstrap critical path for exactly
one package. `cargo` installs metapac and nothing else. kickstart, by contrast,
ships binaries for five platforms.

**What would fix it upstream:** a release workflow. That single change would let
mise fetch metapac directly and collapse two bootstrap steps into one. It is a
better contribution than a personal brew tap, which would help only brew users
and still need someone to maintain it.

### metapac cannot pin versions on most backends

Pinning exists only where a backend's `options` happen to support it: `mise`
(`version`), `cargo` (`git`, `features`, `locked`, `binstall`), `nix`
(`installable`), `uv` (`python`). **apt, brew, dnf and arch have no version
option at all.**

**Consequence:** anything that genuinely needs a pinned version has to come from
mise. This is a large part of why the priority order puts mise first and the OS
package manager late. Of 41 resolved tools here, 23 come from mise.

### metapac does not detect cross-backend duplicates

`metapac unmanaged` lists, per backend, what is installed but undeclared. It
never cross-references that against what you declared under a *different*
backend, so the interesting case is invisible.

**Workaround:** `~/bin/pkg-doctor` does the cross-reference, and also reports
binaries owned by no manager at all and inventory entries that are not
installed. See below.

---

## This machine

### Four tools are installed twice

```
1password    declared via snap, also installed via apt   -> /usr/bin/1password
chezmoi      declared via mise, also installed via snap  -> ~/bin/chezmoi
gh           declared via mise, also installed via apt   -> /usr/bin/gh
ripgrep      declared via mise, also installed via apt   -> mise's copy wins
```

Which one you get depends on `PATH` order and nothing else, and the answer
differs between an interactive shell and a script: `ripgrep` resolves to mise
interactively but to `/usr/bin/rg` from a non-interactive PATH.

Run `pkg-doctor` for the current list. Unresolved deliberately: removing the
apt `1password` may take the desktop application and its SSH signing agent with
it, and `.gitconfig` depends on `/opt/1Password/op-ssh-sign` for commit signing.
Check that before running `apt remove`.

### Thirteen binaries on PATH are owned by no package manager

`pkg-doctor`'s UNOWNED section finds them by asking, for every executable on
PATH, whether any manager claims it. Nothing updates, audits or removes these.

Two actively shadow a declared tool:

- `/usr/local/bin/node` is **v16.17.1, from October 2022**, and wins over the
  mise-declared node 24.18.0 in an interactive shell. It arrived with a
  hand-installed Node toolchain — `npm`, `npx`, `n`, `corepack`, `yarn`,
  `yarnpkg` are all unowned alongside it.
- `/usr/local/bin/starship` came from the upstream `curl | sh`. The inventory
  declares starship under mise, so after `metapac sync` there will be two.

Also unowned: `alacritty`, `anki`, `zutty`, a stray
`libfprint_delete_device_prints.py`, and `/usr/bin/leftwm-theme`, which is a
root-owned symlink into `~/src/github/leftwm/leftwm-theme/target/release/` —
a build directory, so it breaks on `cargo clean`.

None are removed automatically: `/usr/local` is deliberately outside every
package manager's remit, and deleting things there is a decision, not a
cleanup.

### The inventory is Ubuntu- and macOS-shaped

`.bhell` only ever had apt, brew and snap lists, so `arch:` and `dnf:` names are
missing for most tools. Rendering for `linux-arch` or `linux-fedora` today
leaves most of the inventory UNRESOLVED. That is honest output rather than a
bug, but Arch and Fedora support is aspirational until someone fills those in.

### "Not applicable here" and "no data yet" look identical

Rendering for `darwin` reports `build-essential` and `procps` as UNRESOLVED
alongside `1password` and `code`. The first two genuinely do not exist on macOS;
the second two are missing brew cask entries. The output cannot tell them apart.

**Fix:** a `not_applicable: [darwin]` field on a tool, and a template branch
that reports the two categories separately.

### Fonts are declared but nothing installs them

`packages.yaml` has a `fonts:` section. No metapac backend handles fonts, and
nothing else picks them up. macOS could use a brew cask; Linux is a download
into `~/.local/share/fonts`. This is the last of the original requirements with
no implementation.

---

## Gotchas

Not broken, but they will catch you.

### A fresh `mise.toml` is untrusted, and mise ignores it silently

mise refuses to load a config it has not been told to trust, and says nothing
about it — the tools simply never activate. Every scaffold template runs
`mise trust` in a post-gen hook for this reason, and `scaffold --here` runs it
after merging. If you write a `mise.toml` by hand, run `mise trust` yourself.

### Never name a scaffold template file `*.tmpl`

Scaffold templates contain Tera syntax (`{{ project_name }}`) and live inside
the chezmoi source tree. chezmoi renders any source file ending in `.tmpl` as a
*chezmoi* template, which would consume the Tera braces before kickstart ever
saw them. They are plain files with no `.tmpl` suffix, and must stay that way.

Same reason the templates avoid templated directory names: `{{ }}` in a source
path is asking for trouble.

### chezmoi cannot mix `dot_config` and `private_dot_config`

Adding `home/private_dot_config/metapac/` next to the existing
`home/dot_config/` produced:

```
chezmoi: .config: inconsistent state
  (…/home/dot_config, …/home/private_dot_config)
```

One target directory, one source attribute. Everything under `~/.config` uses
`dot_config`.

### ~/.config/mise/config.toml is not managed by chezmoi

It looks like a dotfile and it is not. Both metapac (via `mise use --global`)
and mise itself write to it, so chezmoi managing it would mean every
`metapac sync` created drift that the next `chezmoi apply` reverted — the tools
would be installed and then silently un-declared.

It is generated state, like `~/.config/metapac/`. The inventory is the source of
truth; `run_onchange_after_10-mise-direct.sh.tmpl` reproduces the handful of
entries metapac cannot install.

### The sync hook hashes parsed data, not file bytes

`run_onchange_after_20-metapac-sync.sh.tmpl` embeds
`{{ .packages | toJson | sha256sum }}`. Reformatting `packages.yaml` or editing
a comment will **not** trigger a resync, because the parsed data is unchanged.
This is deliberate. Adding or changing a tool will.

### `metapac unmanaged` output is a valid group file

It prints in group-file format, so adopting an existing machine is mostly
copy-paste. It is also long — 152 unmanaged apt packages here.
