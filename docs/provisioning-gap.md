# The provisioning gap

What this repository does by hand because chezmoi does not do it, written down
so that the tool eventually built to fill the gap is built against real
requirements rather than remembered ones.

Companion to `packages/packages.yaml`, which is the data half of the same
problem, and to the TODO in `~/src/github/highb/.bhell`.

## What chezmoi is good at, and where it stops

chezmoi manages the content of files in `$HOME`: it templates them, keeps them
in git, and makes a second machine converge on the same state. That part works
and should not be replaced.

It stops at the point where a file's content depends on software being
installed. chezmoi has `run_` and `run_onchange_` scripts, but they are just
shell scripts with a naming convention - there is no package model, no
inventory, no dependency ordering, and no way to ask what a machine currently
has. Anything at that layer is a script you wrote, and every dotfiles repo that
grows one grows the same one badly.

## What is currently being worked around

### 1. Every tool integration is guarded because nothing guarantees the tool

`~/.config/shell/tools.sh` runs each integration through `__shell_init`, which
checks `command -v` and swallows failure:

```sh
__shell_init() {
    command -v "$1" >/dev/null 2>&1 || return 0
    ...
}
```

This is the right behaviour for a shell startup file - a missing tool must
never break a terminal - but it is load-bearing in a way it should not be. Of
the tools `shell.yaml` declares, `fd`, `bat`, `eza`, `zoxide` and `atuin` are
not installed on this machine at all. The shell degrades silently, so nobody
finds out. A declared tool that is not installed should be a reportable state,
not a no-op.

### 2. `mise` is doing double duty as a package manager

`home/dot_config/mise/config.toml` pins 16 tools. mise is a runtime version
manager, and using it to install `ripgrep`, `xh` and `awscli` works, but it
means the answer to "where does this binary come from" is different for tools
that are otherwise peers. `fzf` comes from mise; `bat`, if it were installed,
would come from apt.

### 3. Four overlapping sources of software, with no arbitration

This machine can install a given tool four ways, and has used all four:

| Source | Evidence |
| --- | --- |
| `mise` | `dot_config/mise/config.toml`, 16 tools |
| apt / snap | the system; `.bhell` package lists |
| nix | `~/.nix-profile`, `~/.nix-channels`, `nix-profile/bin` on `PATH` |
| curl-to-bash | starship in `/usr/local/bin`, owned by nothing |

Nothing decides which wins. `PATH` order decides, which is why
`__path_prepend` had to be rewritten to move entries to the front rather than
skip them: without that, whichever source ran last won, and bash and zsh
disagreed about which that was.

An abandoned home-manager experiment sits in this repository's history as a
fifth attempt at the same problem.

### 4. Installation is not idempotent, only re-runnable

`.bhell` re-ran unpinned `curl | bash` installers on every setup. Its
idempotence checks were `dpkg -s`, `brew list` and `snap info | grep`, run per
package, each shelling out. There is no notion of a desired state that can be
diffed against an actual state - the chezmoi model, applied to packages, is
exactly what is missing.

### 5. No uninstall

`.bhell/teardown.sh` removes `~/.oh-my-zsh` and then says, in a comment, that
it should remove everything else. `~/.oh-my-zsh` is still on this machine,
sourced by nothing, six months after the zsh config stopped being
framework-based. Removal is the half of convergence that never gets written,
and it is the half that keeps machines honest.

### 6. Things that are neither files nor packages

- **Fonts.** `.bhell` vendored 1.9MB of TTFs and copied them to `~/.fonts`,
  the pre-XDG path.
- **Services.** The flavours config ends in `hook = "systemctl --user reload
  rgbdaemon"`. Something has to own user units and reloads.
- **Colour schemes across applications.** Listed as a TODO in this repo's
  README since it was written. flavours was the previous attempt.
- **GUI applications.** Worth a separate axis: a headless machine wants the
  CLI list and none of `slack`, `discord`, `code`.
- **Platform divergence.** `.bhell` kept one flat list per platform per package
  manager and no mapping between them, so `bat` appeared in three files with no
  indication they were the same thing. `packages.yaml` inverts this: one entry
  per tool, with per-platform names underneath.

## What a tool would have to do

In rough order of how much they matter:

1. **Declarative inventory, diffable.** `plan` and `apply`, not `install`. The
   question "what does this machine have that it should not, and vice versa"
   must be answerable without changing anything.
2. **One entry per tool, many providers.** Cross-platform naming is the whole
   problem; `bat` on apt, `bat` on brew, and `batcat` as the resulting binary
   are three facts about one tool.
3. **Explicit provider precedence.** Given mise, apt, nix and an upstream
   installer can all supply `fzf`, the config must say which one owns it, and
   the tool must notice when something else has also installed it.
4. **Real idempotence.** Query actual state once, compare to desired, act on
   the difference.
5. **Uninstall as a first-class verb**, because otherwise it never gets built.
6. **Beyond packages:** fonts, user services, and file links, with ordering
   between them.
7. **Composability with chezmoi rather than replacement of it.** chezmoi owns
   file content. The tool owns what must exist for that content to work. The
   handoff is `packages.yaml`, and it should stay a plain data file that both
   can read.

## Why a DSL

The reason `.bhell` was bash is that provisioning always has an escape hatch -
a package that needs a flag on one distro, a post-install step, a
platform-specific fallback. A pure data format eventually grows a conditional
and becomes a bad programming language.

An embedded scripting language inverts that: data for the ninety percent that
is a list, real expressions for the rest, in a sandbox that can be evaluated
during `plan` without side effects. That is the argument for rhai, and the
constraint it implies - **evaluation must be side-effect free so that `plan`
is honest** - is the one worth designing around first.
