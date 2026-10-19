# Documentation plan

The goal is to make every supported capability discoverable, reproducible, and
usable locally without LLM assistance, following [AGENTS.md](AGENTS.md).
LLMs can help build and improve the environment; durable code and documentation
must let Brandon operate and maintain it independently.

This is a plan, not a completed documentation audit. Work in the order below;
check off a task only when its documentation and verification evidence exist.

## 1. Inventory and assess coverage

- [ ] Create a capability index in `docs/` and link it from the root README.
  Inventory commands in `home/bin/`, shell aliases and functions, integrations
  in `shell.yaml`, managed application configs, provisioning scripts/hooks,
  package groups, and repository maintenance commands.
- [ ] For each capability, record its purpose, local entry point, source file,
  deployed path, package group, dependencies, supported platforms, canonical
  documentation link, and gaps. Include network, account, and LLM dependencies.
- [ ] Classify coverage as missing, partial, documented, or verified. Record
  verification method and platform separately; a passing Linux check does not
  establish macOS behavior.
- [ ] Review all existing READMEs, `docs/`, and KNOWN_ISSUES.md for stale commands,
  conflicting instructions, unsupported platform claims, and broken links.
  Start with Linux-only wording in `home/bin/README.md` and
  `home/private_README.md`, upstream Neovim setup instructions, and dated package
  ownership counts and provider claims in the root README's TODO section.

Completion: every repository-provided capability has an indexed documentation
destination and an explicit coverage status. Package inventory entries can be
grouped by workflow; locally customized behavior needs its own explanation.

## 2. Establish the documentation contract and navigation

- [ ] Add a reusable workflow documentation template covering purpose, when to
  use it, prerequisites, platform/task availability, setup, exact commands,
  expected results, verification, troubleshooting, maintenance, and recovery.
- [ ] Explain side effects, privilege requirements, network/account dependencies,
  and whether a command changes local files, installs packages, or writes to an
  external service. Use placeholders for secrets and machine-specific values.
- [ ] Define canonical locations: root README for orientation, `docs/` for
  workflows and architecture, nearby READMEs and command help for local use,
  KNOWN_ISSUES.md for confirmed limitations, and this file for outstanding work.
  Link to canonical explanations instead of duplicating them.
- [ ] Make the root README a clear starting point for first setup, everyday use,
  troubleshooting, and extending the environment. Ensure deployed READMEs tell
  the user how to reach the source documentation locally.

Completion: a reader can find the relevant workflow from the root README or
the deployed tool's help without searching chat history.

## 3. Document setup and recovery first

- [ ] Walk through fresh setup on Ubuntu/Debian (including Pop!_OS) and macOS:
  prerequisites, bootstrap, role wizard, preview, apply, installation consent,
  and post-install checks. Clearly distinguish partial Arch/Fedora support
  from primary targets and unsupported deployment targets.
- [ ] Document the machine configuration schema with examples for package groups,
  providers, exclusions, manual provisioning, Git signing, and local overrides.
  Show how to change one field without replacing unrelated settings.
- [ ] Explain chezmoi's source/target model, generated files, reapplying changes,
  importing intentional local edits, updating machines, and what Git commit,
  push, pull, and chezmoi apply each synchronize. Include recovery from drift.
- [ ] Document package resolution and diagnostics: previewing providers,
  unresolved packages, mise PATH/shims, narrowly scoped repairs, and pkg-doctor's
  limitations. Explain ignored files and why deselection does not uninstall.
- [ ] Provide troubleshooting paths for the clipboard (Wayland/X11/macOS and
  headless/SSH), GitHub's `gh` credential helper, signing/1Password, and shell
  startup failures. Include independent local checks and expected output.

Completion: setup, a second apply, and recovery from a representative failure
can be followed from documentation alone, with platform evidence recorded.

## 4. Cover daily tools and workflows

- [ ] Document `pkg-doctor`, `scaffold`, and `vale-as`, including arguments,
  realistic examples, generated/output locations, dependencies, and failures.
- [ ] Document `all_pull.sh` and `gh_clone_all.sh`, including repository scope,
  authentication, network actions, handling of existing work, and recovery.
- [ ] Document `audio_fix.sh` and `gnome_toggle_dark_mode.sh` with their Linux
  desktop/service prerequisites and side effects.
- [ ] Document shell aliases, functions, startup order, PATH, mise, direnv, fzf,
  zoxide, atuin, Starship, local overrides, and integration escape hatches.
- [ ] Document owned Neovim behavior, key entry points, clipboard, plugin/runtime
  downloads, and health checks; distinguish upstream reference material from
  this repository's actual configuration and supported setup.
- [ ] Cover the remaining inventory: terminal/desktop configuration, Git,
  scaffolding templates, writing contexts, cloud/Kubernetes tools, and home
  organization. Link upstream manuals for generic usage and explain local
  defaults, provisioning, and customization here.

Completion: every index entry meets the documentation contract or has an
explicit remaining task. No custom tool relies on chat history for usage.

## 5. Document the augmentation loop

- [ ] Document available LLM entry points and setup, accounts, network needs,
  configuration, and what information is sent externally. Do not embed secrets.
- [ ] Describe a repeatable process: identify a recurring need, implement a
  deterministic local command where possible, verify it, add chezmoi/package
  integration, document it, and use feedback to improve it.
- [ ] Include one worked example from need to independently usable local tool.
  Provide commands for operating, diagnosing, and maintaining it without an LLM.
- [ ] Identify capabilities that inherently require an LLM, explain that
  dependency, and document how to operate the surrounding local tooling when
  the model or network is unavailable.

Completion: Brandon can repeat the augmentation process and use its resulting
tools independently by following repository documentation.

## 6. Verify and prevent documentation drift

- [ ] Follow setup and representative daily workflows in disposable environments
  on Ubuntu and macOS. Record commands, expected/observed results, environment,
  and date; mark untested hardware, GUI, account, or partial-platform steps.
- [ ] Run documented examples with fixtures or dry runs where practical. Keep
  real credentials, workstation changes, and external writes out of automated
  checks; document manual verification for those steps.
- [ ] Add proportionate documentation checks to existing CI: internal links,
  Markdown formatting, and meaningful command/help or fixture checks. Avoid
  tests that merely duplicate implementation or assume a desktop session.
- [ ] Add a contributor checklist requiring documentation/index updates when
  commands, defaults, dependencies, platform support, or setup behavior change.
- [ ] Reconcile outstanding gaps, remove stale instructions, and record remaining
  limitations explicitly before declaring the documentation comprehensive.

Completion: all indexed capabilities meet the contract, supported-platform
verification is recorded with its limits, examples are reproducible, and future
changes have a defined documentation update path.

# Software Supply Chain Verification

- [ ] Do an audit of all packages installed using this tooling. ensure that all package have sha verification/lockfile in place, at a minimum. ideally, all software is signed via cosign, GPG keys, or similar pubkey crypto.
- [ ] Define an agent-augmented upgrade loop that provides an audit process around accepting new package updates w/ options to do a deeper audit of new packages, if warranted. Surface suspicious patterns or changes in packages being upgraded.

# AI Agent Isolation and Configuration

- [ ] Add nono.sh w/ profile configurations for all supported harnesses
- [ ] Ensure that agent-engineering repo is synced properly and visible to all harnesses

