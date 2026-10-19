# Writing and AI applications

Select `writing` for Obsidian and Logseq, and `ai` for Codex CLI, fx, Delta,
and oh-my-pi. Selection is additive through `data.machine.packageGroups` in the
local chezmoi config. It does not require selecting `desktop`. These groups also
request their existing companion tools; see the root README's package table.

## Providers and prerequisites

| App | Linux | macOS | Local entry point |
| --- | --- | --- | --- |
| Obsidian | User Flatpak; Snap fallback when available | Homebrew cask | App launcher; `flatpak run md.obsidian.Obsidian` on Flatpak |
| Logseq | User Flatpak | Homebrew cask | App launcher; `flatpak run com.logseq.Logseq` on Flatpak |
| Codex CLI | mise `codex` native release | Same | `codex` |
| fx coding agent | mise `github:vercel-labs/fx` | Same | `fx` |
| Delta AI app | Repo-owned archive installer, glibc x86_64/ARM64 | Same, Apple Silicon and macOS 13+ | `delta`, `install-delta` |

The Linux Flatpak provider requires `flatpak` already installed. The generated
metapac manifest declares the user Flathub remote and app IDs. If no applicable
provider exists, the package preview reports `UNRESOLVED`; install the prerequisite
or choose an available declared provider. Existing provider priority and explicit
`machine.packageProviders` overrides still apply. Homebrew providers for the
writing apps are restricted to macOS. Intel macOS cannot install Delta through
this integration. Arch/Fedora support remains partial for the overall inventory.

Codex uses mise's registered `codex` tool. fx deliberately uses its full GitHub
name: mise's short `fx` refers to an unrelated JSON utility. Delta deliberately
uses `delta.dev`, not the `git-delta` diff viewer. Neither fx nor Delta executes
a downloaded setup script. Delta downloads and unpacks the application archive
directly using the version-controlled Python tool in `home/bin/`.

Delta's installer requires Python 3.11+ with `tarfile.data_filter` on Linux
(update Python if the check fails), curl, and the normal platform extraction
tools. macOS uses built-in `ditto` and `codesign`. It installs under the current
user without sudo or shell startup edits. Linux desktop/runtime libraries must
also satisfy Delta's requirements; the installer does not install OS libraries.

## Provision through chezmoi

Use the existing host-role wizard, or merge `writing` and `ai` into the current
`data.machine.packageGroups` list without replacing other machine settings.

```sh
chezmoi execute-template '{{ includeTemplate "package-plan" . }}'
chezmoi diff
DOTFILES_INSTALL_PACKAGES=1 chezmoi apply
```

The last command authorizes all selected packages, not just these additions.
Ordinary interactive apply previews and asks for installation consent.
`packageExcludes` can exclude individual apps. `manualProvisioning: true`
disables installation hooks, including Delta's. File application still deploys
`~/bin/install-delta` for the `ai` group. Deselecting a role does not uninstall
existing software or erase notes, settings, accounts, or conversations.

For a narrow manual installation on Linux with mise and Flatpak available:

```sh
chezmoi apply --include=files,dirs ~/bin/install-delta ~/.config/metapac
mise use --global codex
mise use --global github:vercel-labs/fx
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub md.obsidian.Obsidian com.logseq.Logseq
install-delta --dry-run
install-delta
```

These commands make network requests and install software for the current user.
macOS users can substitute `brew install --cask obsidian logseq` for the Flatpak
steps. Run the same mise and `install-delta` commands on supported Macs.

## Verify and start locally

```sh
command -v codex fx delta install-delta
codex --version
fx --version
install-delta --status
```

Expect mise-managed Codex/fx executables or shims and a Delta CLI link under
`~/.local/bin`. `install-delta --status` performs no network requests and prints
the bundle path, CLI path, installation presence, and archive receipt if present.
On Linux, verify the writing apps with:

```sh
flatpak info --user md.obsidian.Obsidian
flatpak info --user com.logseq.Logseq
```

On macOS, use `brew list --cask obsidian logseq`. Launch each writing app and
create or open a local vault/graph. Note storage and backups remain your choice;
chezmoi does not manage your notes or app login state. Linux's Logseq Flatpak
currently follows the file-based release; Homebrew may ship a different release
track. Back up an existing graph before opening it with a different track.

Run `codex` and follow its sign-in prompts. Run `fx login` (or `fx login codex`
for a ChatGPT subscription), then `fx` in a project; `fx doctor` diagnoses setup.
Run `delta` and follow its account/model setup; Delta requires a Zed account and
acceptance of its early-access agreement. Authentication is a separate user step;
provisioning never copies credentials into the repository.

Installing these tools and using their help/diagnostics requires no LLM
assistance. Agent work needs a configured model and may send project context to
the chosen provider. fx can connect to a local model; installing fx does not
install one. Review each app's permissions and provider settings before starting
a task. Obsidian/Logseq local editing works independently of an LLM.

## Control Delta installation and updates

`install-delta` reuses an existing standard-path installation by default. It does
not repeatedly download or upgrade it during apply. Close Delta before replacing
its bundle. All of these commands can be run locally without an LLM:

```sh
install-delta --help
install-delta --dry-run                  # Resolve latest; no installation
install-delta --status                   # Inspect local receipt offline
install-delta --upgrade                  # Explicitly replace with latest
install-delta --version 0.20.1 --dry-run  # Inspect a specific release URL
```

To reproduce a recorded archive, pass its version and recorded digest:

```sh
install-delta --upgrade --version VERSION --sha256 SHA256
```

Replace `VERSION` and `SHA256` with values from a previously reviewed receipt.
The checksum is checked before extraction. Without `--sha256`, the tool records
the downloaded digest but does not authenticate it against an independently
published checksum. Downloads use HTTPS, release metadata must match the
expected versioned vendor URL, and macOS bundle signatures are checked for
integrity. No downloaded shell scripts are executed or quarantine flags removed.

The receipt is `.dotfiles-install.json` inside `~/.local/delta.app` on Linux or
`~/Applications/Delta.app` on macOS. It records version, URL, platform, and SHA256.
The installer stages a new bundle before replacing the old one and restores the
old bundle on a failed swap. Its Linux desktop entry is
`~/.local/share/applications/dev.zed.Delta.desktop`. Upstream app self-updates
are separate from this install process and can make the receipt historical;
consult the app's own version display and update settings.

Update Codex with `mise upgrade codex` and fx with
`mise upgrade github:vercel-labs/fx`; use mise version selection to pin either
tool when desired. The current direct hook requests fx `@latest` on provisioning.
Update writing apps through their selected package manager. Avoid independently
installing a second copy through a different provider.

## Troubleshooting and recovery

- Missing commands: start a new managed shell and check `command -v mise`,
  `mise ls`, and PATH. The shell configuration supplies `~/bin` and
  `~/.local/bin`; mise activation supplies its tools.
- Flatpak failures: inspect `flatpak remotes --user` and confirm the app IDs
  above. The user Flathub remote must exist even if a system remote exists.
- `fx` opens a JSON utility: inspect `command -v fx` and `mise ls`. Select
  `github:vercel-labs/fx`, resolve PATH/ownership conflicts, and start a new shell.
- Delta CLI conflict: the installer refuses to replace an unrelated file or
  symlink at `~/.local/bin/delta`. Inspect it and relocate the conflicting tool
  intentionally, then rerun installation. Do not point a Git diff configuration
  at this AI app if it expects git-delta.
- Delta metadata/layout or signature errors: leave the existing installation
  intact, inspect the official release/download page, and update this installer
  only after verifying the new layout. Use a recorded version/digest to recover
  a prior release with `--upgrade`.
- Missing Python or unsupported platform: install the documented prerequisites
  or exclude Delta for that machine. The package preview leaves unavailable
  providers unresolved rather than selecting another product.
- Auth/model failures: use app diagnostics and sign-in flows. Keep keys and
  account state machine-local. A successful installation does not establish
  account entitlement, network availability, or model configuration.

## Sources and validation

Provider details were checked against the official
[Codex CLI documentation](https://developers.openai.com/codex/cli/),
[fx source](https://github.com/vercel-labs/fx),
[Delta installation guide](https://delta.dev/docs/installation),
[Obsidian cask](https://formulae.brew.sh/cask/obsidian),
[Logseq cask](https://formulae.brew.sh/cask/logseq), and Flathub manifests for
[Obsidian](https://github.com/flathub/md.obsidian.Obsidian) and
[Logseq](https://github.com/flathub/com.logseq.Logseq).

Local automated checks:

```sh
python3 -B -m unittest discover -s tests -p test_package_groups.py -v
python3 -B -m unittest discover -s tests -p test_delta_install.py -v
python3 -B -m unittest discover -s tests -p test_deployment.py -v
```

These use temporary homes, fake package managers, and fixture archives. GUI
startup, account setup, and macOS installation need separate manual validation;
passing these checks alone does not establish them.

Host verification on Pop!_OS 24.04, x86_64 (2026-10-19): Codex 0.163.0,
fx 0.0.14, and Delta 0.20.1 reported their versions successfully. Obsidian
1.14.4 was already installed through user Flathub; Logseq 0.10.15 was installed
and confirmed in the user Flatpak inventory. All 62 relevant package, deployment,
Delta installer, and existing vendor-provisioning tests passed. The deployed
installer and package manifests have no chezmoi diff. macOS installation and
GUI/account setup have not been exercised in this session.
